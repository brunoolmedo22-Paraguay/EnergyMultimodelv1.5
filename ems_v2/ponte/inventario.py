"""Contrato de integração com o Gestor de Microrredes (3C-0 §3.1): instantâneo do inventário de UMA microrrede.

Princípios:

* **Identidade inequívoca.** A microrrede é identificada pelo UID do catálogo (32 hex) + incarnação + revisão salva
  do documento e suas impressões digitais. Todo dispositivo carrega o UID da microrrede a que pertence: misturar
  dispositivos de microrredes diferentes num mesmo instantâneo é ERRO detectável (``dispositivo_de_outra_microrrede``).
* **Por dispositivo, sem agregação.** Cada registro do inventário (``eq-…``) e cada arranjo FV (``arr-…``) é um
  dispositivo com seus próprios valores. Nada é somado entre registros: a agregação de "tipos equivalentes" do
  adaptador V1.6 (``seeds2.microgrid.adapter``) NÃO é usada aqui e não pode substituir a configuração por dispositivo.
  Unidades físicas idênticas declaradas DENTRO de um registro (``count``/``quantity``) são preservadas como
  ``quantidade``; a expansão em ``UIDRecurso(equipamento, unidade=k)`` para geradores despacháveis é explícita
  (``recursos_ems``).
* **Presença × habilitação × disponibilidade.** ``presente`` (no inventário ativo) × ``retirado`` (só o UID, em
  ``retirados``); ``habilitado`` é decisão do inventário; ``disponivel``/``indisponivel`` é condição do CENÁRIO
  (``cenario.CondicaoInicialDispositivo``), nunca do inventário.
* **Procedência por valor.** Cada valor guarda a origem (declarado no inventário, valor inicial SUGERIDO pelo SEEDS2,
  catálogo de referência, derivado, ausente, sintético), o caminho no documento de origem e a ``Procedencia`` (3A).
  Ausente é ``None`` com origem ``ausente`` — nunca zero.

Nada aqui importa ``seeds2``: o adaptador real está em ``ems_v2.ponte_seeds2``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..contracts import RE_EQUIPAMENTO, UIDRecurso
from ..diagnostics import Constatacao, RelatorioValidacao, aviso, erro
from ..provenance import Procedencia, validar_procedencia
from . import CONTRATO_VERSAO
from .canonico import sha256

RE_MICRORREDE = re.compile(r"^([0-9a-f]{32}|syn-[a-z0-9][a-z0-9_-]{0,39})$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

TIPOS_DISPOSITIVO = {
    "pv_usina": "Usina fotovoltaica (agrupador de arranjos; sem parâmetros elétricos próprios)",
    "pv_arranjo": "Arranjo fotovoltaico (recurso renovável modelado)",
    "eolica": "Aerogerador(es) idênticos de um registro",
    "bateria": "Banco de baterias",
    "pemfc": "Bloco de sistemas PEMFC idênticos",
    "termica": "Unidade térmica",
}
PAPEIS_EMS = {"agrupador": "Sem decisão própria", "renovavel": "Potencial renovável (M03)",
              "armazenamento": "Armazenamento (M06–M08)", "gerador": "Geração despachável (M10, M14–M16)"}
PAPEL_POR_TIPO = {"pv_usina": "agrupador", "pv_arranjo": "renovavel", "eolica": "renovavel", "bateria": "armazenamento",
                  "pemfc": "gerador", "termica": "gerador"}
TECNOLOGIA_EMS = {"pv_arranjo": "fv", "eolica": "eolica", "pemfc": "pemfc", "termica": "termica"}
ORIGENS_VALOR = {
    "inventario_declarado": "Digitado no inventário da microrrede (rastreável à revisão; sem documento de origem)",
    "inventario_sugerido_seeds2": "Valor inicial SUGERIDO pelo SEEDS2 e não confirmado (não sustenta valor físico)",
    "catalogo_referencia": "Catálogo/modelo de referência do software (não medido nesta instalação)",
    "derivado": "Derivado de outros valores por relação registrada em ``derivacao``",
    "cenario": "Condição do cenário operativo (não do inventário)",
    "sintetico": "Sintético — exclusivo para ensaio",
    "ausente": "Ausente (não declarado); nenhum valor é presumido",
}
PRESENCAS = ("presente",)


@dataclass(frozen=True)
class AssociacaoModelo:
    """Associação dispositivo ↔ modelo: o modelo científico existente que o representa e o papel no EMS V2."""
    modelo_cientifico: str              # p. ex. "models.pv_module" (descrição; nada é importado)
    referencia: str | None              # chave do catálogo/perfil (módulo FV, aerogerador, célula, perfil PEMFC)
    papel_ems: str                      # chave de PAPEIS_EMS
    tecnologia_ems: str | None = None   # "fv" | "eolica" | "pemfc" | "termica" | None


@dataclass(frozen=True)
class ValorInventario:
    """Um valor da fonte, como declarado, com origem e procedência. Exatamente um de ``numero``/``texto``/``logico``
    é preenchido — ou nenhum, quando ``origem == "ausente"``."""
    chave: str
    unidade_fonte: str                  # unidade DECLARADA pela fonte ("%", "kWh", "R$/MWh", "" para texto)
    caminho_fonte: str                  # caminho no documento de origem
    origem: str                         # chave de ORIGENS_VALOR
    procedencia: Procedencia | None
    numero: float | None = None
    texto: str | None = None
    logico: bool | None = None
    derivacao: str = ""                 # relação aplicada (origem derivado/catálogo)

    @property
    def presente(self) -> bool:
        return self.origem != "ausente" and (self.numero is not None or self.texto is not None or self.logico is not None)


@dataclass(frozen=True)
class DispositivoInventario:
    uid: str
    microrrede_uid: str
    tipo: str
    nome: str
    tag: str
    habilitado: bool
    presenca: str
    pai: str | None
    quantidade: int | None              # unidades físicas idênticas declaradas no registro; None = não se aplica
    modelo: AssociacaoModelo
    valores: tuple[ValorInventario, ...]
    impressao_digital: str              # SHA-256 da física do registro na fonte

    def valor(self, chave: str) -> ValorInventario | None:
        return next((v for v in self.valores if v.chave == chave), None)


@dataclass(frozen=True)
class IdentidadeMicrorrede:
    uid: str
    incarnacao: str | None
    revisao_config: int
    impressao_config: str               # SHA-256 do documento salvo (revisão)
    impressao_inventario: str           # SHA-256 do inventário FÍSICO ativo (mesma regra do Piso 2A)
    nome: str


@dataclass(frozen=True)
class InventarioMicrorrede:
    versao_contrato: int
    identidade: IdentidadeMicrorrede
    modo_operacao: str | None           # declarado na instalação (isolada/conectada/...); None = não declarado
    conexao_rede: str | None
    dispositivos: tuple[DispositivoInventario, ...]
    retirados: tuple[str, ...]          # UIDs retirados (registro de auditoria; não operáveis)
    procedencia: Procedencia | None
    observacoes: tuple[str, ...] = field(default_factory=tuple)

    def dispositivo(self, uid: str) -> DispositivoInventario | None:
        return next((d for d in self.dispositivos if d.uid == uid), None)

    def uids(self) -> set[str]:
        return {d.uid for d in self.dispositivos}


# ------------------------------------------------------------------------------------------------ validação
def _valor(v: ValorInventario, cam: str) -> list[Constatacao]:
    out: list[Constatacao] = []
    if v.origem not in ORIGENS_VALOR:
        out.append(erro("origem_valor_invalida", cam, f"Origem {v.origem!r} desconhecida."))
    preenchidos = [x for x in (v.numero, v.texto, v.logico) if x is not None]
    if len(preenchidos) > 1:
        out.append(erro("valor_ambiguo", cam, "Mais de um tipo de valor preenchido."))
    if v.numero is not None and (isinstance(v.numero, bool) or not isinstance(v.numero, (int, float))
                                 or v.numero != v.numero or v.numero in (float("inf"), float("-inf"))):
        out.append(erro("valor_nao_finito", cam, "Valor numérico NaN/Inf ou não numérico (ausente = None)."))
    if v.origem == "ausente":
        if preenchidos:
            out.append(erro("ausente_com_valor", cam, "Origem 'ausente' com valor preenchido."))
        return out
    if not preenchidos:
        out.append(erro("valor_sem_conteudo", cam, f"Origem {v.origem!r} sem valor (use origem 'ausente')."))
    if v.origem == "inventario_sugerido_seeds2":
        out += validar_procedencia(v.procedencia, cam + ".procedencia", sustenta_valor=False)
    else:
        out += validar_procedencia(v.procedencia, cam + ".procedencia", sustenta_valor=v.numero is not None)
    if v.origem in ("derivado", "catalogo_referencia") and not v.derivacao.strip():
        out.append(erro("derivacao_nao_registrada", cam, "Valor derivado/de catálogo sem relação registrada."))
    if v.origem == "sintetico" and v.procedencia is not None and v.procedencia.tipo != "sintetico":
        out.append(erro("sintetico_rotulado_como_real", cam, "Valor de origem sintética com procedência não sintética."))
    if v.procedencia is not None and v.procedencia.tipo == "sintetico" and v.origem != "sintetico":
        out.append(erro("sintetico_rotulado_como_real", cam, "Procedência sintética com origem não sintética."))
    return out


def validar_inventario(inv: InventarioMicrorrede) -> RelatorioValidacao:
    out: list[Constatacao] = []
    if inv.versao_contrato != CONTRATO_VERSAO:
        out.append(erro("versao_contrato_incompativel", "versao_contrato", f"{inv.versao_contrato!r}."))
    idt = inv.identidade
    if not isinstance(idt.uid, str) or not RE_MICRORREDE.fullmatch(idt.uid):
        out.append(erro("microrrede_uid_invalido", "identidade.uid", f"{idt.uid!r}."))
    if isinstance(idt.revisao_config, bool) or not isinstance(idt.revisao_config, int) or idt.revisao_config < 1:
        out.append(erro("revisao_invalida", "identidade.revisao_config", f"{idt.revisao_config!r}."))
    for nome in ("impressao_config", "impressao_inventario"):
        if not _HEX64.fullmatch(str(getattr(idt, nome))):
            out.append(erro("impressao_invalida", f"identidade.{nome}", "SHA-256 inválido."))
    out += validar_procedencia(inv.procedencia, "procedencia", sustenta_valor=False)
    vistos: dict[str, int] = {}
    tipos = {d.uid: d.tipo for d in inv.dispositivos}
    for i, d in enumerate(inv.dispositivos):
        cam = f"dispositivos[{d.uid}]"
        if not isinstance(d.uid, str) or not RE_EQUIPAMENTO.fullmatch(d.uid):
            out.append(erro("uid_invalido", cam + ".uid", f"{d.uid!r}."))
        if d.uid in vistos:
            out.append(erro("uid_duplicado", cam, f"UID repetido (posições {vistos[d.uid]} e {i})."))
        vistos.setdefault(d.uid, i)
        if d.microrrede_uid != idt.uid:
            out.append(erro("dispositivo_de_outra_microrrede", cam + ".microrrede_uid",
                            f"Dispositivo da microrrede {d.microrrede_uid!r} no instantâneo de {idt.uid!r}."))
        if d.uid in inv.retirados:
            out.append(erro("dispositivo_retirado_ativo", cam, "UID consta como retirado e como presente."))
        if d.tipo not in TIPOS_DISPOSITIVO:
            out.append(erro("tipo_dispositivo_invalido", cam + ".tipo", f"{d.tipo!r}."))
            continue
        if d.presenca not in PRESENCAS:
            out.append(erro("presenca_invalida", cam + ".presenca", f"{d.presenca!r}."))
        if not isinstance(d.habilitado, bool):
            out.append(erro("habilitado_invalido", cam + ".habilitado", "Exigido verdadeiro/falso."))
        if d.modelo.papel_ems != PAPEL_POR_TIPO[d.tipo]:
            out.append(erro("papel_incoerente", cam + ".modelo.papel_ems",
                            f"Tipo {d.tipo} exige papel {PAPEL_POR_TIPO[d.tipo]!r}; recebido {d.modelo.papel_ems!r}."))
        if d.modelo.tecnologia_ems != TECNOLOGIA_EMS.get(d.tipo):
            out.append(erro("tecnologia_incoerente", cam + ".modelo.tecnologia_ems", f"{d.modelo.tecnologia_ems!r}."))
        if d.tipo == "pv_arranjo":
            if d.pai is None or tipos.get(d.pai) != "pv_usina":
                out.append(erro("arranjo_sem_usina", cam + ".pai", "Arranjo FV exige usina FV existente como pai."))
        elif d.pai is not None:
            out.append(erro("pai_indevido", cam + ".pai", "Somente arranjos FV têm pai."))
        q = d.quantidade
        if q is not None and (isinstance(q, bool) or not isinstance(q, int) or q < 1):
            out.append(erro("quantidade_invalida", cam + ".quantidade", f"Exigido inteiro >= 1 ou None; recebido {q!r}."))
        if not _HEX64.fullmatch(str(d.impressao_digital)):
            out.append(erro("impressao_invalida", cam + ".impressao_digital", "SHA-256 inválido."))
        chaves: set[str] = set()
        for v in d.valores:
            if v.chave in chaves:
                out.append(erro("valor_duplicado", f"{cam}.valores[{v.chave}]", "Chave repetida."))
            chaves.add(v.chave)
            out += _valor(v, f"{cam}.valores[{v.chave}]")
    if not inv.dispositivos:
        out.append(aviso("inventario_vazio", "dispositivos", "Inventário sem dispositivos."))
    return RelatorioValidacao(tuple(out))


def hash_inventario(inv: InventarioMicrorrede) -> str:
    return sha256(inv)


# ------------------------------------------------------------------------------------------------ recursos EMS
def recursos_ems(d: DispositivoInventario) -> tuple[UIDRecurso, ...]:
    """Identidades de recurso do contrato 3A para um dispositivo, sem inventar identificadores.

    * agrupador (usina FV): nenhum recurso;
    * renovável e armazenamento: UM recurso por registro (o potencial/estado declarado é do registro);
    * gerador despachável com ``quantidade`` q > 1: q unidades ``eq-…#1..q`` (commitment é POR UNIDADE em 3C-1);
      com q = 1 ou None: um recurso."""
    papel = PAPEL_POR_TIPO.get(d.tipo)
    if papel == "agrupador":
        return ()
    if papel == "gerador" and d.quantidade is not None and d.quantidade > 1:
        return tuple(UIDRecurso(d.uid, k) for k in range(1, d.quantidade + 1))
    return (UIDRecurso(d.uid),)


__all__ = ["AssociacaoModelo", "DispositivoInventario", "IdentidadeMicrorrede", "InventarioMicrorrede", "ORIGENS_VALOR",
           "PAPEIS_EMS", "PAPEL_POR_TIPO", "RE_MICRORREDE", "TECNOLOGIA_EMS", "TIPOS_DISPOSITIVO", "ValorInventario",
           "hash_inventario", "recursos_ems", "validar_inventario"]
