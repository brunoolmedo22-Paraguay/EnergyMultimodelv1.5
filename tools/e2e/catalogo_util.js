// UI-FINISH-01: os cartões do Catálogo (Gestor) vêm RECOLHIDOS — detalhe e ações com display: none até o usuário
// expandir (hover com mouse, clique/toque ou Enter/Espaço no convite «Passe o mouse ou clique para expandir»). Os
// roteiros anteriores ao UI-FINISH-01 interagem com as ações dos cartões; antes disso, expandem TODOS os cartões como o
// usuário faria (o estado aberto do <details> do convite). Nenhuma ação é acionada aqui.
async function expandirCartoes(alvo) {
  const p = typeof alvo.page === "function" ? alvo.page() : alvo;      // aceita a página ou um localizador dela
  await p.locator(".gc-tg").first().waitFor({ timeout: 120000 }).catch(() => {});
  await p.evaluate(() => document.querySelectorAll("details.gc-x:not([open])").forEach((d) => { d.open = true; }));
  await p.waitForTimeout(200);
}
module.exports = { expandirCartoes };
