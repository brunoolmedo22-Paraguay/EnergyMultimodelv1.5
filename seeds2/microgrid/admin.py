"""Proteção da EXCLUSÃO DEFINITIVA de microrredes (sem Streamlit; testável).

O SEEDS2 não tem contas nem perfis: as microrredes são registros da instalação, compartilhados entre sessões.
A exclusão definitiva é a única ação irreversível do Gestor e, por isso:

* com credencial administrativa configurada (variável de ambiente ``SEEDS2_ADMIN_PASSWORD`` ou
  ``seeds2_admin_password`` em Streamlit Secrets) → a credencial é exigida a cada exclusão
  (comparação em tempo constante, no servidor; o valor nunca é enviado ao navegador);
* sem credencial, ``SEEDS2_DEV_MODE=1`` → modo de desenvolvimento LOCAL explícito: exclusão sem credencial
  (somente para uso em máquina própria);
* sem credencial e sem modo de desenvolvimento → exclusão DESATIVADA (padrão seguro para implantações
  compartilhadas/públicas).
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import Callable, Mapping

ENV_PASSWORD = "SEEDS2_ADMIN_PASSWORD"
ENV_DEV_MODE = "SEEDS2_DEV_MODE"
SECRET_KEY = "seeds2_admin_password"


@dataclass(frozen=True)
class DeletionPolicy:
    mode: str                 # "protected" | "dev" | "disabled"
    secret: str | None = field(default=None, repr=False)     # nunca exibido/registrado

    @property
    def allowed(self) -> bool:
        return self.mode in ("protected", "dev")

    @property
    def needs_credential(self) -> bool:
        return self.mode == "protected"

    def describe(self) -> str:
        if self.mode == "protected":
            return "Exclusão protegida por credencial administrativa (configurada no servidor)."
        if self.mode == "dev":
            return ("Modo de desenvolvimento local (SEEDS2_DEV_MODE=1): exclusão sem credencial. Não use este modo em "
                    "implantações compartilhadas.")
        return ("A exclusão definitiva está desativada nesta implantação. Configure a credencial administrativa "
                f"({ENV_PASSWORD} ou '{SECRET_KEY}' em Streamlit Secrets) ou, somente em uso local, {ENV_DEV_MODE}=1.")

    def check(self, provided: str | None) -> bool:
        if self.mode == "dev":
            return True
        if self.mode != "protected" or not self.secret or not isinstance(provided, str) or not provided:
            return False
        return hmac.compare_digest(provided.encode("utf-8"), self.secret.encode("utf-8"))


def deletion_policy(environ: Mapping[str, str], secret_getter: Callable[[], str | None] | None = None) -> DeletionPolicy:
    secret = (environ.get(ENV_PASSWORD) or "").strip() or None
    if secret is None and secret_getter is not None:
        try:
            got = secret_getter()
        except Exception:  # noqa: BLE001 — sem arquivo de secrets: equivale a não configurado
            got = None
        secret = got.strip() if isinstance(got, str) and got.strip() else None
    if secret:
        return DeletionPolicy("protected", secret)
    if (environ.get(ENV_DEV_MODE) or "").strip() == "1":
        return DeletionPolicy("dev")
    return DeletionPolicy("disabled")
