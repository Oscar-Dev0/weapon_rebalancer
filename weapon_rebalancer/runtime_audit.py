from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


SOURCE_EXTENSIONS = {'.lua', '.js', '.ts', '.jsx', '.tsx', '.cs'}
SKIP_DIRECTORIES = {
    '.git', '.svn', '.hg', '__pycache__', 'node_modules', 'vendor',
    'dist', 'build', '.cache', 'cache', 'stream', 'html', 'web',
}


@dataclass(frozen=True)
class PatternSpec:
    code: str
    severity: str
    description: str
    pattern: re.Pattern[str]


@dataclass
class RuntimeFinding:
    code: str
    severity: str
    path: str
    line: int
    description: str
    snippet: str


@dataclass
class RuntimeAuditReport:
    root: str
    files_scanned: int = 0
    findings: list[RuntimeFinding] = field(default_factory=list)
    hard_blockers: int = 0
    warnings: int = 0
    info: int = 0

    def add(self, finding: RuntimeFinding) -> None:
        self.findings.append(finding)
        if finding.severity == 'hard':
            self.hard_blockers += 1
        elif finding.severity == 'warning':
            self.warnings += 1
        else:
            self.info += 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

    def print_summary(self) -> None:
        print('[RUNTIME AUDIT]')
        print(f'ROOT: {self.root}')
        print(f'Archivos de código escaneados: {self.files_scanned}')
        print(f'Bloqueos duros: {self.hard_blockers} | warnings: {self.warnings} | info: {self.info}')
        if not self.findings:
            print('No se encontraron conflictos conocidos en el código visible.')
            return
        for finding in self.findings[:160]:
            marker = 'X' if finding.severity == 'hard' else ('!' if finding.severity == 'warning' else 'i')
            print(f'  [{marker}] {finding.code} | {finding.path}:{finding.line}')
            print(f'      {finding.description}')
            print(f'      {finding.snippet}')


CRITICAL_CALL_PATTERN = re.compile(
    r'\b(?:SetPedSuffersCriticalHits|SET_PED_SUFFERS_CRITICAL_HITS|API\.SetPedSuffersCriticalHits)\s*\(((?:[^()]|\([^()]*\)){1,500})\)',
    re.IGNORECASE | re.DOTALL,
)


PATTERNS: tuple[PatternSpec, ...] = (
    PatternSpec(
        code='critical_hits_disabled',
        severity='hard',
        description='Este código desactiva los multiplicadores críticos. Un disparo a la cabeza pasa a comportarse como daño corporal.',
        pattern=re.compile(
            r'\b(?:SetPedSuffersCriticalHits|SET_PED_SUFFERS_CRITICAL_HITS|API\.SetPedSuffersCriticalHits)\s*\(.{0,500}?,\s*false\s*\)',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    PatternSpec(
        code='critical_hits_disabled_native_hash',
        severity='hard',
        description='Invocación por hash que desactiva critical hits (0xEBD76F2359F190AC).',
        pattern=re.compile(
            r'\b(?:Citizen\.)?(?:InvokeNative|invokeNative)\s*\(\s*(?:0x)?EBD76F2359F190AC\b.{0,500}?,\s*false\s*\)',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    PatternSpec(
        code='critical_hits_disabled_csharp_hash',
        severity='hard',
        description='Llamada C# al native de critical hits con false.',
        pattern=re.compile(
            r'\bFunction\.Call.{0,500}?(?:SET_PED_SUFFERS_CRITICAL_HITS|EBD76F2359F190AC).{0,500}?false',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    PatternSpec(
        code='weapon_damage_forced_zero',
        severity='hard',
        description='Un modificador runtime está llevando el daño de armas a cero; el META no puede compensar un multiplicador final en cero.',
        pattern=re.compile(
            r'\b(?:SetPlayerWeaponDamageModifier|SET_PLAYER_WEAPON_DAMAGE_MODIFIER|SetWeaponDamageModifierThisFrame|SET_WEAPON_DAMAGE_MODIFIER_THIS_FRAME)\s*\(.{0,500}?,\s*0(?:\.0+)?\s*\)',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    PatternSpec(
        code='critical_hits_enabled',
        severity='info',
        description='Este recurso intenta habilitar critical hits. Revisa el orden si otro recurso también los desactiva.',
        pattern=re.compile(
            r'\b(?:SetPedSuffersCriticalHits|SET_PED_SUFFERS_CRITICAL_HITS|API\.SetPedSuffersCriticalHits)\s*\(.{0,500}?,\s*true\s*\)',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    PatternSpec(
        code='ped_armour_write',
        severity='warning',
        description='Este recurso escribe armadura del ped. Puede explicar ropa/chalecos que recuperan protección después del disparo.',
        pattern=re.compile(r'\b(?:SetPedArmour|SET_PED_ARMOUR|AddArmourToPed|ADD_ARMOUR_TO_PED)\s*\(', re.IGNORECASE),
    ),
    PatternSpec(
        code='ped_health_write',
        severity='warning',
        description='Este recurso escribe vida del ped. Revisa si restaura salud durante CEventNetworkEntityDamage o dentro de un loop.',
        pattern=re.compile(r'\b(?:SetEntityHealth|SET_ENTITY_HEALTH)\s*\(', re.IGNORECASE),
    ),
    PatternSpec(
        code='runtime_damage_modifier',
        severity='warning',
        description='Este recurso modifica daño en runtime y puede sobrescribir el balance del META.',
        pattern=re.compile(
            r'\b(?:SetPlayerWeaponDamageModifier|SET_PLAYER_WEAPON_DAMAGE_MODIFIER|SetWeaponDamageModifierThisFrame|SET_WEAPON_DAMAGE_MODIFIER_THIS_FRAME)\s*\(',
            re.IGNORECASE,
        ),
    ),
)


def _mask_comments(text: str, suffix: str) -> str:
    """Replace comments with spaces while preserving line numbers and offsets."""
    chars = list(text)

    def blank(match: re.Match[str]) -> None:
        for index in range(match.start(), match.end()):
            if chars[index] not in {'\n', '\r'}:
                chars[index] = ' '

    if suffix == '.lua':
        for match in re.finditer(r'--\[\[.*?\]\]', text, re.DOTALL):
            blank(match)
        interim = ''.join(chars)
        for match in re.finditer(r'--[^\r\n]*', interim):
            blank(match)
    else:
        for match in re.finditer(r'/\*.*?\*/', text, re.DOTALL):
            blank(match)
        interim = ''.join(chars)
        for match in re.finditer(r'//[^\r\n]*', interim):
            blank(match)
    return ''.join(chars)


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative_parts = path.relative_to(root).parts[:-1]
        if any(part.lower() in SKIP_DIRECTORIES for part in relative_parts):
            continue
        yield path


def _line_number(text: str, offset: int) -> int:
    return text.count('\n', 0, offset) + 1


def _line_snippet(text: str, line: int) -> str:
    lines = text.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:300]
    return ''


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _add_dynamic_critical_hit_findings(report: RuntimeAuditReport, path: Path, root: Path, original: str, masked: str) -> None:
    for match in CRITICAL_CALL_PATTERN.finditer(masked):
        args = match.group(1)
        if ',' not in args:
            continue
        toggle = args.rsplit(',', 1)[-1].strip().lower()
        if toggle in {'true', 'false'}:
            continue
        line = _line_number(masked, match.start())
        report.add(RuntimeFinding(
            code='critical_hits_dynamic_toggle',
            severity='warning',
            path=_relative(path, root),
            line=line,
            description=f'Critical hits usa un valor dinámico ({toggle[:80]}). Confirma que nunca termine en false para jugadores.',
            snippet=_line_snippet(original, line),
        ))


def _add_correlated_findings(report: RuntimeAuditReport, path: Path, root: Path, original: str, masked: str) -> None:
    lower = masked.lower()
    has_damage_event = 'ceventnetworkentitydamage' in lower or 'weapondamageevent' in lower or 'gameeventtriggered' in lower
    if not has_damage_event:
        return

    cancel_match = re.search(r'\bCancelEvent\s*\(\s*\)', masked, re.IGNORECASE)
    if cancel_match and 'weapondamageevent' in lower:
        line = _line_number(masked, cancel_match.start())
        report.add(RuntimeFinding(
            code='weapon_damage_event_cancelled',
            severity='hard',
            path=_relative(path, root),
            line=line,
            description='El archivo escucha weaponDamageEvent y llama CancelEvent(); puede cancelar completamente el daño antes del META.',
            snippet=_line_snippet(original, line),
        ))

    restore_match = re.search(r'\b(?:SetEntityHealth|SetPedArmour|AddArmourToPed)\s*\(', masked, re.IGNORECASE)
    if restore_match:
        line = _line_number(masked, restore_match.start())
        report.add(RuntimeFinding(
            code='damage_event_health_or_armour_restore',
            severity='hard',
            path=_relative(path, root),
            line=line,
            description='El mismo archivo procesa eventos de daño y vuelve a escribir vida/armadura. Es un candidato directo a antitank.',
            snippet=_line_snippet(original, line),
        ))


def scan_runtime_conflicts(root: Path) -> RuntimeAuditReport:
    root = root.resolve()
    report = RuntimeAuditReport(root=str(root))
    if not root.exists() or not root.is_dir():
        raise ValueError(f'Ruta runtime inválida: {root}')

    seen: set[tuple[str, str, int]] = set()
    for path in _iter_source_files(root):
        report.files_scanned += 1
        try:
            original = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        masked = _mask_comments(original, path.suffix.lower())

        for spec in PATTERNS:
            for match in spec.pattern.finditer(masked):
                line = _line_number(masked, match.start())
                key = (spec.code, str(path), line)
                if key in seen:
                    continue
                seen.add(key)
                report.add(RuntimeFinding(
                    code=spec.code,
                    severity=spec.severity,
                    path=_relative(path, root),
                    line=line,
                    description=spec.description,
                    snippet=_line_snippet(original, line),
                ))

        _add_dynamic_critical_hit_findings(report, path, root, original, masked)
        _add_correlated_findings(report, path, root, original, masked)

    severity_rank = {'hard': 0, 'warning': 1, 'info': 2}
    report.findings.sort(key=lambda item: (severity_rank.get(item.severity, 9), item.path.lower(), item.line, item.code))
    return report
