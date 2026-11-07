"""SEEDS2 Piso 2D-A — Arquivo Científico Portátil (sem interface e sem ciência).

* ``format``   — contrato versionado do pacote ``.seeds2study.zip`` (estrutura, nomes seguros, limites) e a INSPEÇÃO de
  um pacote não confiável (integridade SHA-256, tamanhos, relações entre cenário, versões, inventário, previsões e
  rodadas) — nunca executa nada do arquivo;
* ``exporter`` — monta o pacote a partir de UM instantâneo de leitura da microrrede (``MicrogridStore.snapshot``);
* ``store``    — ``ArchiveStore``: estudos arquivados da INSTALAÇÃO (banco próprio, separado dos bancos das
  microrredes e do catálogo), importação atômica, somente leitura (triggers);
* ``view``     — leitura de um estudo arquivado (versões, inventário, previsões, rodadas e séries) sem recalcular.

Três entidades distintas: **cenário operativo** (editável, versionado, na microrrede), **rodada científica** (imutável,
na microrrede) e **estudo arquivado** (representação portátil e autocontida de um cenário com todas as suas versões,
dependências e rodadas; somente leitura). Abrir, navegar ou importar um estudo NUNCA chama modelos nem o otimizador.
"""
