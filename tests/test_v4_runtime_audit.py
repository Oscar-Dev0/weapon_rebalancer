from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from weapon_rebalancer.runtime_audit import scan_runtime_conflicts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeAuditV4Tests(unittest.TestCase):
    def test_detects_critical_hits_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / 'client.lua'
            script.write_text(
                "CreateThread(function()\n while true do\n  SetPedSuffersCriticalHits(PlayerPedId(), false)\n  Wait(0)\n end\nend)\n",
                encoding='utf-8',
            )
            report = scan_runtime_conflicts(root)
            self.assertEqual(report.hard_blockers, 1)
            self.assertTrue(any(item.code == 'critical_hits_disabled' for item in report.findings))

    def test_detects_multiline_critical_hits_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'client.lua').write_text(
                "SetPedSuffersCriticalHits(\n  PlayerPedId(),\n  false\n)\n",
                encoding='utf-8',
            )
            report = scan_runtime_conflicts(root)
            self.assertTrue(any(item.code == 'critical_hits_disabled' for item in report.findings))

    def test_warns_about_dynamic_critical_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'client.lua').write_text(
                "SetPedSuffersCriticalHits(PlayerPedId(), Config.AllowCriticalHits)\n",
                encoding='utf-8',
            )
            report = scan_runtime_conflicts(root)
            self.assertTrue(any(item.code == 'critical_hits_dynamic_toggle' for item in report.findings))

    def test_ignores_commented_false_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'client.lua').write_text(
                "-- SetPedSuffersCriticalHits(PlayerPedId(), false)\nSetPedSuffersCriticalHits(PlayerPedId(), true)\n",
                encoding='utf-8',
            )
            report = scan_runtime_conflicts(root)
            self.assertEqual(report.hard_blockers, 0)
            self.assertTrue(any(item.code == 'critical_hits_enabled' for item in report.findings))

    def test_detects_damage_event_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'antitank.lua').write_text(
                "AddEventHandler('gameEventTriggered', function(name, args)\n"
                " if name == 'CEventNetworkEntityDamage' then\n"
                "  SetEntityHealth(PlayerPedId(), 200)\n"
                " end\nend)\n",
                encoding='utf-8',
            )
            report = scan_runtime_conflicts(root)
            self.assertTrue(any(item.code == 'damage_event_health_or_armour_restore' for item in report.findings))
            self.assertGreaterEqual(report.hard_blockers, 1)

    def test_guard_never_writes_health_armour_or_manual_damage(self) -> None:
        client = (PROJECT_ROOT / 'extras' / 'os_headshot_guard' / 'client.lua').read_text(encoding='utf-8')
        forbidden = ('SetEntityHealth(', 'SetPedArmour(', 'AddArmourToPed(', 'ApplyDamageToPed(', 'CancelEvent(')
        for token in forbidden:
            self.assertNotIn(token, client)
        self.assertIn('SetPedSuffersCriticalHits(ped, true)', client)

    def test_recommended_v4_profile_does_not_use_extreme_armour_multiplier(self) -> None:
        profile = json.loads((PROJECT_ROOT / 'profiles' / 'rebelion_real_onetap_v4.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['modules']['armour'], 'configured')
        self.assertEqual(profile['headshot']['helmet_multiplier'], 1.0)
        self.assertGreaterEqual(profile['headshot']['target_effective_health'], 1000.0)
        self.assertTrue(profile['validation']['require_runtime_critical_hits'])


if __name__ == '__main__':
    unittest.main()
