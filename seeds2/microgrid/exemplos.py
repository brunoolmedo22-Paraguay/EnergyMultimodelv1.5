"""Exemplos persistentes do SEEDS2 — restauração automática das instantâneas versionadas em ``seeds2/exemplos/``.

Decisão do responsável (missão «Exemplos persistentes», 14/11/2026): o SEEDS2 é entregue com microrredes de exemplo
(os casos C1–C5 do caderno de roteiros) que precisam sobreviver ao reinício do Streamlit Cloud, cujo disco é
efímero. As instantâneas completas (``.seeds2snapshot.zip``, geradas pelo botão GUARDAR COMPLETO do Gestor) são
colocadas no repositório pelos responsáveis; ao iniciar, o SEEDS2 restaura no catálogo as que estiverem faltando.

Regras:

* **idempotente**: microrrede já presente no catálogo (mesma identidade) NÃO é tocada — as alterações feitas durante
  a execução do servidor ficam até o próximo reinício, quando o exemplo volta ao estado guardado (decisão: exemplos
  EDITÁVEIS, para que os usuários experimentem);
* **sem duplicatas**: a identidade é a da instantânea; duas sessões que iniciem juntas não criam duas cópias (o
  catálogo recusa a segunda e ela é contada como «presente»);
* **nunca impede a aplicação de abrir**: toda falha vira relato (``Relato.falhas``), registrado no log do servidor
  e mostrado no Gestor;
* só lê arquivos do diretório de exemplos do código (``SEEDS2_EXEMPLOS_DIR`` permite apontar outro diretório em
  testes); ``SEEDS2_EXEMPLOS=0`` desliga a restauração (a suíte de testes a desliga por padrão).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import snapshot as S

ENV_ENABLE = "SEEDS2_EXEMPLOS"
ENV_DIR = "SEEDS2_EXEMPLOS_DIR"
DEFAULT_DIR = Path(__file__).resolve().parents[1] / "exemplos"
NOTE_PREFIX = "Exemplo do SEEDS2 restaurado automaticamente"


@dataclass
class Relato:
    restaurados: list[str] = field(default_factory=list)      # «arquivo (uid)»
    presentes: list[str] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)            # «arquivo: motivo»


def habilitado() -> bool:
    return os.environ.get(ENV_ENABLE, "1").strip().lower() not in {"0", "false", "no", "nao", "não", "off"}


def diretorio() -> Path:
    raw = os.environ.get(ENV_DIR, "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_DIR


def arquivos(pasta: Path | None = None) -> list[Path]:
    pasta = pasta or diretorio()
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.is_file() and not p.is_symlink() and p.name.endswith(S.SUFFIX))


def eh_exemplo(entry) -> bool:
    """A entrada do catálogo foi restaurada de um exemplo do código?"""
    return str(getattr(entry, "note", "") or "").startswith(NOTE_PREFIX)


def garantir(reg, pasta: Path | None = None) -> Relato:
    """Restaura no catálogo ``reg`` toda instantânea de exemplo cuja microrrede não esteja presente."""
    from .registry import RegistryError

    rel = Relato()
    for path in arquivos(pasta):
        try:
            if path.stat().st_size > S.MAX_PACKAGE_BYTES:
                rel.falhas.append(f"{path.name}: arquivo maior que o limite (512 MiB)")
                continue
            data = path.read_bytes()
        except OSError as exc:
            rel.falhas.append(f"{path.name}: não foi possível ler ({exc})")
            continue
        rep = S.inspect_snapshot(data)
        if not rep.ok:
            rel.falhas.append(f"{path.name}: " + " | ".join(rep.errors))
            continue
        uid = rep.uid
        if reg.exists(uid):
            rel.presentes.append(f"{path.name} ({uid})")
            continue
        try:
            reg.import_snapshot(data, note=f"{NOTE_PREFIX} de seeds2/exemplos/{path.name} "
                                           f"(instantânea de {str(rep.manifest.get('created_at'))[:40]}, "
                                           f"revisão {rep.manifest.get('revision')}).")
            rel.restaurados.append(f"{path.name} ({uid})")
        except RegistryError as exc:
            if reg.exists(uid):                                 # outra sessão restaurou no mesmo instante
                rel.presentes.append(f"{path.name} ({uid})")
            else:
                rel.falhas.append(f"{path.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 — um exemplo defeituoso nunca derruba a aplicação
            rel.falhas.append(f"{path.name}: {type(exc).__name__}: {str(exc)[:300]}")
    return rel


def garantir_na_inicializacao(reg) -> Relato:
    """Chamado UMA vez por processo ao abrir o catálogo. Nunca levanta exceção."""
    if not habilitado():
        return Relato()
    try:
        rel = garantir(reg)
    except Exception as exc:  # noqa: BLE001
        rel = Relato(falhas=[f"restauração dos exemplos interrompida: {type(exc).__name__}: {str(exc)[:300]}"])
    if rel.restaurados or rel.falhas:
        print(f"[SEEDS2] exemplos: restaurados={rel.restaurados} presentes={len(rel.presentes)} falhas={rel.falhas}",
              file=sys.stderr, flush=True)
    return rel
