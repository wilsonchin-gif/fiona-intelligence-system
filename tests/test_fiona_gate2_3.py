from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from app.fiona_alert_runtime import make_price_event, process_alert_events
from app.fiona_memory import FionaMemory
from app.fiona_runtime import run_once, run_scheduler_cycle
from app.fiona_scheduler import SchedulerLedger, ScheduledOccurrence, clear_uncertain_occurrences, can_execute_occurrence, write_uncertain_delivery_journal
from app.fiona_briefing import FionaBriefKind
from app.fiona_state import RuntimeStatePaths, StateContinuityError, atomic_write_json, initialize_state
from app.fiona_state_migration import migrate_bundle


def instant(value="2026-10-09T20:20:00+08:00"):
    return datetime.fromisoformat(value)


def fake_runner(**kwargs):
    return {"ok": True, "brief_push": {"ok": True, "message_ids": [12345], "errors": []}}


class PersistentStateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "volume/fiona"
        self.output = Path(self.temporary.name) / "container/reports"
        self.env = patch.dict(os.environ, {"FIONA_STATE_DIR": str(self.root)}, clear=True)
        self.env.start()
        initialize_state(self.root, ledger_payload=SchedulerLedger(Path("unused")).to_dict(),
                         memory_payload=FionaMemory().to_dict(), boundary=instant())
        self.paths = RuntimeStatePaths.from_environment(self.output)
        self.runner = Mock(side_effect=fake_runner)

    def tearDown(self):
        clear_uncertain_occurrences()
        self.env.stop()
        self.temporary.cleanup()

    def cycle(self, when="2026-10-09T20:34:00+08:00", output=None):
        return run_scheduler_cycle(output_dir=output or self.output, send=True, timezone_name="Asia/Hong_Kong", now=instant(when), runner=self.runner)

    def test_delivered_occurrence_is_durable(self):
        self.cycle()
        ledger = SchedulerLedger.load(self.paths.ledger)
        self.assertEqual(next(iter(ledger.entries.values()))["status"], "success")
        self.assertEqual(self.runner.call_count, 1)

    def test_process_restart_same_occurrence_not_resent(self):
        self.cycle()
        self.cycle("2026-10-09T20:50:00+08:00")
        self.assertEqual(self.runner.call_count, 1)

    def test_redeploy_new_container_uses_same_volume(self):
        self.cycle()
        self.cycle("2026-10-09T20:50:00+08:00", Path(self.temporary.name)/"replacement/reports")
        self.assertEqual(self.runner.call_count, 1)

    def test_instance_replacement_has_no_old_backlog_burst(self):
        self.cycle()
        for minute in range(50, 60):
            self.cycle(f"2026-10-09T20:{minute}:00+08:00", Path(self.temporary.name)/"other")
        self.assertEqual(self.runner.call_count, 1)

    def test_next_future_task_remains_eligible(self):
        self.cycle()
        self.cycle("2026-10-09T22:35:00+08:00")
        self.assertEqual([call.kwargs["brief"] for call in self.runner.call_args_list], ["evening", "daily"])

    def test_legitimate_catch_up_unchanged(self):
        self.assertEqual(self.cycle("2026-10-09T20:50:00+08:00")["occurrence_results"][0]["status"], "success")
        self.assertTrue(self.runner.call_args.kwargs["send"])

    def test_expired_catch_up_is_not_sent(self):
        result = self.cycle("2026-10-09T23:10:00+08:00")
        self.assertNotIn("evening", [call.kwargs["brief"] for call in self.runner.call_args_list])
        self.assertTrue(result["ok"])

    def test_arbitration_retains_existing_winner(self):
        result = self.cycle("2026-10-09T22:35:00+08:00")
        self.assertEqual([call.kwargs["brief"] for call in self.runner.call_args_list], ["daily"])
        self.assertTrue(any(item["action"] == "suppress" for item in result["arbitration"]))

    def test_missing_initialized_ledger_blocks_replay(self):
        self.paths.ledger.unlink()
        result = self.cycle()
        self.assertFalse(result["ok"])
        self.assertIn("unexpected_missing", result["ledger_load_error"])
        self.runner.assert_not_called()
        self.assertFalse(self.paths.ledger.exists())

    def test_corrupt_ledger_is_not_overwritten_or_used(self):
        self.paths.ledger.write_text("{bad")
        result = self.cycle()
        self.assertFalse(result["ok"])
        self.runner.assert_not_called()
        self.assertEqual(self.paths.ledger.read_text(), "{bad")

    def test_missing_memory_blocks_both_brief_and_alert(self):
        self.paths.memory.unlink()
        self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_corrupt_memory_blocks(self):
        self.paths.memory.write_text("null")
        self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_manifest_missing_is_not_new_install(self):
        (self.root/"state_manifest.json").unlink()
        self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_uninitialized_volume_is_explicitly_blocked(self):
        with patch.dict(os.environ, {"FIONA_STATE_DIR": str(self.root/"empty")}):
            self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_partial_temp_file_is_never_authoritative(self):
        self.cycle()
        self.paths.ledger.with_suffix(".json.tmp").write_text("{bad")
        self.cycle("2026-10-09T20:50:00+08:00")
        self.assertEqual(self.runner.call_count, 1)

    def test_atomic_replace_failure_preserves_authoritative_file(self):
        before = self.paths.ledger.read_bytes()
        with patch("app.fiona_state.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                atomic_write_json(self.paths.ledger, {"bad": "payload"})
        self.assertEqual(self.paths.ledger.read_bytes(), before)

    def test_memory_atomic_failure_preserves_cooldown(self):
        before=self.paths.memory.read_bytes()
        with patch("app.fiona_state.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(StateContinuityError):
                FionaMemory().save(self.paths.memory)
        self.assertEqual(self.paths.memory.read_bytes(),before)

    def test_memory_write_failure_never_uses_legacy_send_fallback(self):
        from app.fiona_surface_validation import en_us_fixture_snapshot
        with patch("app.fiona_memory.atomic_write_json",side_effect=OSError("disk full")), patch("app.fiona_runtime.push_text") as send:
            result=run_once(output_dir=self.output,brief="evening",send=True,snapshot_builder=lambda now:en_us_fixture_snapshot())
        self.assertFalse(result["ok"])
        self.assertFalse(result["fallback"]["used"])
        send.assert_not_called()

    def test_standalone_memory_write_failure_never_sends(self):
        send=Mock()
        with patch("app.fiona_memory.atomic_write_json",side_effect=OSError("disk full")):
            with self.assertRaises(StateContinuityError):
                process_alert_events([make_price_event(instant(),"BTC",-1.8,["BTC"],"BTC move")],self.output,send_func=send,enabled=True,dry_run=False)
        send.assert_not_called()

    def test_runtime_alert_memory_not_reset_by_replacement_output(self):
        from app.fiona_runtime import build_payload
        from app.fiona_surface_validation import en_us_fixture_snapshot
        first=build_payload(en_us_fixture_snapshot(),instant(),self.paths.memory,"evening","en-US")
        before=set(FionaMemory.load(self.paths.memory).event_memory)
        replacement=RuntimeStatePaths.from_environment(self.output/"new_container")
        second=build_payload(en_us_fixture_snapshot(),instant()+timedelta(minutes=5),replacement.memory,"evening","en-US")
        self.assertEqual(before,set(FionaMemory.load(replacement.memory).event_memory))
        self.assertFalse(second.alert_messages)

    def test_alert_intent_is_persisted_before_mock_delivery(self):
        def fake(text):
            self.assertTrue(FionaMemory.load(self.paths.standalone_alert_memory).event_memory)
            return {"ok":True,"result":{"message_id":99}}
        process_alert_events([make_price_event(instant(),"BTC",-1.8,["BTC"],"BTC move")],self.output,send_func=fake,enabled=True,dry_run=False)

    def test_safe_recovery_boundary_allows_future_not_old_backlog(self):
        recovered=Path(self.temporary.name)/"recovery/fiona"
        initialize_state(recovered,ledger_payload=SchedulerLedger(Path("unused")).to_dict(),memory_payload=FionaMemory().to_dict(),boundary=instant("2026-10-09T21:00:00+08:00"),provenance="explicit_safe_activation_boundary")
        with patch.dict(os.environ,{"FIONA_STATE_DIR":str(recovered)}):
            self.cycle("2026-10-09T21:05:00+08:00")
            self.runner.assert_not_called()
            self.cycle("2026-10-09T22:35:00+08:00")
        self.assertEqual([call.kwargs["brief"] for call in self.runner.call_args_list],["daily"])

    def test_invalid_semantic_ledger_is_blocked(self):
        atomic_write_json(self.paths.ledger,{"schema_version":"1.0","last_check_at":None,"entries":{"x":{}}})
        self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_invalid_schema_version_is_blocked(self):
        atomic_write_json(self.paths.ledger,{"schema_version":"999","entries":{}})
        self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_fsync_precedes_replace(self):
        events=[]
        original_replace=os.replace
        with patch("app.fiona_state.os.fsync", side_effect=lambda fd: events.append("fsync")), patch("app.fiona_state.os.replace", side_effect=lambda a,b: (events.append("replace"), original_replace(a,b))):
            atomic_write_json(self.paths.ledger, SchedulerLedger(Path("unused")).to_dict())
        self.assertLess(events.index("fsync"), events.index("replace"))

    def test_unknown_delivery_record_survives_restart(self):
        occ = ScheduledOccurrence.create(FionaBriefKind.EVENING, instant("2026-10-09T20:30:00+08:00"), instant("2026-10-09T20:34:00+08:00"))
        ledger=SchedulerLedger.load(self.paths.ledger)
        ledger.mark_unknown_delivery_state(occ, occ.detected_at, "unknown result")
        ledger.save()
        self.cycle()
        self.runner.assert_not_called()

    def test_uncertain_journal_survives_process_memory_loss(self):
        write_uncertain_delivery_journal(self.paths.uncertain_journal, {"occurrence_id":"evening:2026-10-09T20:30:00+08:00"})
        clear_uncertain_occurrences()
        self.cycle()
        self.runner.assert_not_called()

    def test_railway_requires_real_volume(self):
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_ID":"production"}), patch("app.fiona_state.os.path.ismount", return_value=False):
            self.assertFalse(self.cycle()["ok"])
        self.runner.assert_not_called()

    def test_railway_mounted_path_is_used(self):
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_ID":"production", "RAILWAY_VOLUME_MOUNT_PATH":str(self.root.parent)}), patch("app.fiona_state.os.path.ismount", return_value=True):
            self.assertTrue(self.cycle()["ok"])

    def test_state_outside_volume_is_rejected(self):
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_ID":"production", "RAILWAY_VOLUME_MOUNT_PATH":"/data"}), patch("app.fiona_state.os.path.ismount", return_value=True):
            self.assertFalse(self.cycle()["ok"])

    def test_direct_run_once_cannot_bypass_guard(self):
        self.paths.ledger.unlink()
        builder=Mock()
        result=run_once(output_dir=self.output, send=True, snapshot_builder=builder)
        self.assertFalse(result["ok"])
        builder.assert_not_called()

    def test_alert_cooldown_and_lifecycle_survive_restart(self):
        send=Mock(return_value={"ok":True,"result":{"message_id":99}})
        event=make_price_event(instant(),"BTC",-1.8,["BTC","ETH","SOL"],"BTC move")
        first=process_alert_events([event], self.output, send_func=send, enabled=True,dry_run=False)
        repeated=make_price_event(instant()+timedelta(minutes=10),"BTC",-1.8,["BTC","ETH","SOL"],"BTC move")
        second=process_alert_events([repeated], self.output/"replacement", send_func=send,enabled=True,dry_run=False)
        self.assertTrue(first[0].sent)
        self.assertFalse(second[0].sent)
        self.assertEqual(send.call_count,1)
        self.assertIsNotNone(FionaMemory.load(self.paths.standalone_alert_memory).event_memory[event.event_family_id].last_pushed_at)

    def test_alert_new_material_change_remains_eligible(self):
        send=Mock(return_value={"ok":True,"result":{"message_id":99}})
        first=make_price_event(instant(),"BTC",-1.8,["BTC","ETH","SOL"],"BTC move")
        process_alert_events([first],self.output,send_func=send,enabled=True,dry_run=False)
        updated=make_price_event(instant()+timedelta(minutes=61),"BTC",-3.8,["BTC","ETH","SOL"],"BTC larger move")
        updated.evidence.append("new_cross_market_confirmation")
        updated.impact_score=10
        updated.urgency_score=10
        result=process_alert_events([updated],self.output,send_func=send,enabled=True,dry_run=False)
        self.assertTrue(result[0].sent)
        self.assertEqual(send.call_count,2)

    def test_migration_refuses_overwrite(self):
        with self.assertRaises(StateContinuityError):
            initialize_state(self.root,ledger_payload=SchedulerLedger(Path("unused")).to_dict(),memory_payload=FionaMemory().to_dict(),boundary=instant())

    def test_migration_preserves_entries_and_bounds_unknown_backlog(self):
        self.cycle()
        target=Path(self.temporary.name)/"other_volume/fiona"
        original=json.loads(self.paths.ledger.read_text())
        initialize_state(target,ledger_payload=original,memory_payload=FionaMemory().to_dict(),boundary=instant("2026-10-09T21:00:00+08:00"))
        migrated=SchedulerLedger.load(target/"scheduler/ledger.json")
        self.assertEqual(migrated.entries,original["entries"])
        self.assertEqual(migrated.last_check_at,instant("2026-10-09T21:00:00+08:00"))

    def test_new_os_processes_redeploy_simulation(self):
        code='''import json,sys
from pathlib import Path
from datetime import datetime
from app.fiona_runtime import run_scheduler_cycle
calls=[]
def fake(**kwargs):
    calls.append(kwargs['brief'])
    return {'ok':True,'brief_push':{'ok':True,'message_ids':[12345],'errors':[]}}
s=run_scheduler_cycle(output_dir=Path(sys.argv[1]),send=True,timezone_name='Asia/Hong_Kong',now=datetime.fromisoformat(sys.argv[2]),runner=fake)
print(json.dumps({'calls':calls,'ok':s['ok']}))'''
        for when,expected in (("2026-10-09T20:34:00+08:00",["evening"]),("2026-10-09T20:50:00+08:00",[]),("2026-10-09T22:35:00+08:00",["daily"])):
            process=subprocess.run([sys.executable,"-c",code,str(self.output/when[:16].replace(":","")),when],capture_output=True,text=True,check=True,env=os.environ.copy())
            result=json.loads(process.stdout)
            self.assertTrue(result["ok"])
            self.assertEqual(result["calls"],expected)


if __name__ == "__main__":
    unittest.main()
