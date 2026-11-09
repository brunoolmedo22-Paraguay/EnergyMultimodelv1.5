# Rastreabilidade dos sete equipamentos

Pacote original intacto: `evidencia/SEEDS2_CODEX_7_EOLICAS_INPUT.zip`. Contém README, handoff, validação Work, PDF de rastreabilidade, candidatos, dataset, resultados, manifesto NREL, sete CSV e quatro PDF. Os candidatos não são executados em produção. Somente os sete autorizados foram incorporados.

Arquivo NREL/NatLabRockies verificado via Git HTTPS em `e9e4ccc6a87f50c0c65d236154a2897e752c47c9`; os quatro CSV coincidem byte a byte e por SHA de blob. Licença BSD-3-Clause retida em `config/wind_curves/NREL_LICENSE.txt`. YAML secundários originais preservados em `evidencia/`. Os textos das páginas arquivadas no ZIP atribuem as curvas a ensaios SWCC/NREL; os YAML dizem `theoretical`: divergência conservada, sem nova classificação como ensaio primário verificado.

## Estado

| Equipamento | Referência kW | Pico kW | Domínio m/s | Estado |
|---|---:|---:|---|---|
| Vergnet GEV MP C 275 kW | 275 | 275.0 | [2.5, 25.0] | restricted_domain |
| Vestas V47-660 kW | 660 | 660.0 | [4.0, 25.0] | restricted_domain |
| Vestas V52-850 kW OptiSpeed | 850 | 850.0 | [4.0, 25.0] | restricted_domain |
| Bergey Excel 10 | 8.9 | 12.555 | [0.5, 20.5] | curve_analysis_only |
| Bergey Excel 15 | 15.6 | 20.611 | [1.0, 16.47] | curve_analysis_only |
| Kestrel e400nb | 2.5 | 3.025 | [0.59, 19.49] | curve_analysis_only |
| SWIFT | 1 | 1.43 | [0.54, 23.99] | curve_analysis_only |

## Vergnet GEV MP C 275 kW
- Identidade: Vergnet / GEV MP C 275 kW; variante: None. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 275 kW; definição: `{'kind': 'manufacturer_nominal', 'relative_tolerance': 0.01}`. Pico 275 kW; 21 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 32 m; área 804.0 m²; altura selecionada None; opções [55, 60]. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 3.5 m/s; cut-out 25; re-cut-in None. rho 1.225 kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida 0.0 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: DC-11-00-01-EN_GEV_MP-C_275_kW.pdf; páginas PDF 7; SHA documento 05e8d865be60bbb96e9968c96edc6ca221fc5879c25c3c4eab4439d89ea79efa.
- Referência/versão: DC-11-00-01-EN; pie 04.14; https://www.vergnet.com/wp-content/uploads/2023/06/DC-11-00-01-EN_GEV_MP-C_275_kW.pdf; SHA256=05e8d865be60bbb96e9968c96edc6ca221fc5879c25c3c4eab4439d89ea79efa
- Fonte primária: https://www.vergnet.com/wp-content/uploads/2023/06/DC-11-00-01-EN_GEV_MP-C_275_kW.pdf
- Arquivo: PDF dentro do pacote Work; revisão: DC-11-00-01-EN; pie 04.14; https://www.vergnet.com/wp-content/uploads/2023/06/DC-11-00-01-EN_GEV_MP-C_275_kW.pdf; SHA256=05e8d865be60bbb96e9968c96edc6ca221fc5879c25c3c4eab4439d89ea79efa; SHA blob None.
- CSV: `config/wind_curves/vergnet275.csv`; SHA-256 `0b0a1665ade82a117fbaa496eaecb041f8643b01c50170116aa5f74a69b3cccc`; domínio [2.5, 25.0]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: None; erro relativo 0.00000000%; filtro numérico 1%: True; aprovação: manufacturer_table_verified_against_work.
- Qualidade: {'cut_in': 'manufacturer_spec', 'rated_wind_speed': 'derived_from_curve_first_rated_point', 'cut_out': 'manufacturer_spec', 'power_curve': 'exact_manufacturer_table'}; fronteira elétrica: {'quantity': 'manufacturer_electrical_power_curve', 'measurement_point': None, 'measurement_point_label': 'Punto eléctrico exacto no informado', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': False, 'confidence': 'measurement_point_not_provided'}.
- Limitações: LISTO PARA INCORPORACIÓN. Tabla oficial eléctrica a 1.225 kg/m³, dominio hasta 25 m/s y meseta 12..25 explícita. V nominal se deriva a 12 m/s; no se atribuye al fabricante como especificación publicada. No se asigna una clase individual entre II y IV: debe elegirse la configuración de sitio. Tabla: 275 kW a 12 m/s y hasta 25 m/s. El punto 25,275 representa la rama operativa, antes del disparo; SEEDS2 pone cero para v>=25. Frontera: tabla de potencia eléctrica del aerogenerador, medición exacta no explicitada. No deducir de la mención de transformador en gabinete que sus pérdidas están incluidas.

## Vestas V47-660 kW
- Identidade: Vestas / V47-660 kW; variante: single_generator_690V_50Hz. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 660 kW; definição: `{'kind': 'manufacturer_nominal', 'relative_tolerance': 0.01}`. Pico 660 kW; 16 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 47 m; área 1735.0 m²; altura selecionada None; opções [40, 45, 50, 55]. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 4 m/s; cut-out 25; re-cut-in 20. rho 1.225 kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida 2.9 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: Vestas_V47.pdf; páginas PDF 12; SHA documento 0aaf05e8c558f936f671759744ca56ae6ca2f9c6e8f9186783ca18ab76f1cad1.
- Referência/versão: 943111.R4, 02-05-00; pág. impresa 6 = pág. PDF 12; https://sti2d.ecolelamache.org/ressources/EE/premiere/TP/serie%202/Vestas_V47.pdf; SHA256=0aaf05e8c558f936f671759744ca56ae6ca2f9c6e8f9186783ca18ab76f1cad1
- Fonte primária: https://sti2d.ecolelamache.org/ressources/EE/premiere/TP/serie%202/Vestas_V47.pdf
- Arquivo: PDF dentro do pacote Work; revisão: 943111.R4, 02-05-00; pág. impresa 6 = pág. PDF 12; https://sti2d.ecolelamache.org/ressources/EE/premiere/TP/serie%202/Vestas_V47.pdf; SHA256=0aaf05e8c558f936f671759744ca56ae6ca2f9c6e8f9186783ca18ab76f1cad1; SHA blob None.
- CSV: `config/wind_curves/vestas47.csv`; SHA-256 `3a7afbfe22b48409e3056f498973bc18217828e5face9c8826514e3760591171`; domínio [4.0, 25.0]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: None; erro relativo 0.00000000%; filtro numérico 1%: True; aprovação: manufacturer_table_verified_against_work.
- Qualidade: {'cut_in': 'manufacturer_spec', 'rated_wind_speed': 'manufacturer_spec', 'cut_out': 'manufacturer_spec', 'power_curve': 'exact_manufacturer_table'}; fronteira elétrica: {'quantity': 'manufacturer_electrical_power_curve', 'measurement_point': None, 'measurement_point_label': 'Punto eléctrico exacto no informado', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': False, 'confidence': 'measurement_point_not_provided'}.
- Limitações: LISTO PARA INCORPORACIÓN. Tabla oficial de la versión de un generador, rho=1.225; rango 19..25 publicado explícitamente. No mezclar con V47-660/200. Curva tabulada calculada por el fabricante a partir de perfiles NACA63.600/FFA-W3 y TI=10%, viento medio 10 min a buje y normal al rotor. No es un ajuste teórico creado para esta misión. No confundir tabla calculada p.PDF12 con medición TWE de apéndice ni con variante de dos generadores p.PDF14. V nominal publicada 15 m/s (folleto p.PDF4): P(15)=657 kW (99.55%). Primera velocidad >=99% a 15; primer valor exactamente 660 a 17. Rearranque 20 m/s en p.PDF10 (impresa4). SEEDS2 registra el dato pero no simula histéresis; idóneo para balance energético estático, no para validar secuencias de parada/rearranque.

## Vestas V52-850 kW OptiSpeed
- Identidade: Vestas / V52-850 kW OptiSpeed; variante: OptiSpeed_104.2_dBA. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 850 kW; definição: `{'kind': 'manufacturer_nominal', 'relative_tolerance': 0.01}`. Pico 850 kW; 16 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 52 m; área 2124.0 m²; altura selecionada None; opções [40, 44, 49, 55, 60, 65]. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 4 m/s; cut-out 25; re-cut-in 20. rho 1.225 kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida 25.5 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: V52-850kWh%20Gen%20Spec-1-1.pdf; páginas PDF 8; SHA documento 39e52a04fd0733c0deef916e18f91d1c5edca1ea10a37e681a14a59b19f34263.
- Referência/versão: 946506 V10, 2008-10-08; https://mkwind.pl/uploads/filemanager/PDF/V52-850kWh%20Gen%20Spec-1-1.pdf; SHA256=39e52a04fd0733c0deef916e18f91d1c5edca1ea10a37e681a14a59b19f34263
- Fonte primária: https://mkwind.pl/uploads/filemanager/PDF/V52-850kWh%20Gen%20Spec-1-1.pdf
- Arquivo: PDF dentro do pacote Work; revisão: 946506 V10, 2008-10-08; https://mkwind.pl/uploads/filemanager/PDF/V52-850kWh%20Gen%20Spec-1-1.pdf; SHA256=39e52a04fd0733c0deef916e18f91d1c5edca1ea10a37e681a14a59b19f34263; SHA blob None.
- CSV: `config/wind_curves/vestas52.csv`; SHA-256 `5efdf48fdf02356ac8b1176437f83023d89ea7db5a78e43edbf9b584e11ca52f`; domínio [4.0, 25.0]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: None; erro relativo 0.00000000%; filtro numérico 1%: True; aprovação: manufacturer_table_verified_against_work.
- Qualidade: {'cut_in': 'manufacturer_spec', 'rated_wind_speed': 'derived_from_curve_first_rated_point', 'cut_out': 'manufacturer_spec', 'power_curve': 'exact_manufacturer_table'}; fronteira elétrica: {'quantity': 'manufacturer_electrical_power_curve', 'measurement_point': 'ground_controller_low_voltage_side_of_transformer', 'measurement_point_label': 'Controlador a nivel de suelo, lado de baja tensión del transformador (p.PDF7)', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': False, 'confidence': 'manufacturer_explicit'}.
- Limitações: LISTO PARA INCORPORACIÓN. Tabla oficial a 1.225 kg/m³ y modo acústico 104.2 dB(A). Rango 18..25 expresamente constante. V nominal inferida, sin mezclar otras curvas acústicas. Curvas/tablas calculadas oficialmente con perfiles NACA63/FFA-W3. No son mediciones nuevas ni una curva genérica cúbica. Curva nominal seleccionada: ruido 104.2 dB(A), TI=10%, viento medio 10 minutos a buje perpendicular al plano del rotor. No usar tablas 103/102/101/100 dB(A). Frontera publicada p.PDF7: excluye pérdidas del transformador y cables de alta tensión. No reaplicar eficiencias de rotor/caja/generador. V nominal no fijada en la tabla seleccionada: primer >=99% a 15 m/s; primer valor exactamente 850 a 17 m/s. Se propone 17 derivada (criterio alcance exacto). Rearranque 20 m/s p.PDF6. El modelo actual no representa histéresis ni ventanas de control de 10 minutos.

## Bergey Excel 10
- Identidade: Bergey / Excel 10; variante: None. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 8.9 kW; definição: `{'kind': 'archive_reference_at_wind_speed', 'wind_speed_mps': 11.0, 'relative_tolerance': 0.01, 'verification_status': 'pending_primary_document'}`. Pico 12.555 kW; 41 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 7 m; área 38.48451000647496 m²; altura selecionada None; opções []. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 2.5 m/s; cut-out None; re-cut-in None. rho None kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida -0.012 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: SWCC-10-12-Summary-Report.pdf; páginas PDF []; SHA documento None.
- Referência/versão: NREL/NatLabRockies e9e4ccc6a87f50c0c65d236154a2897e752c47c9; https://smallwindcertification.org/wp-content/uploads/2019/12/SWCC-10-12-Summary-Report.pdf
- Fonte primária: https://smallwindcertification.org/wp-content/uploads/2019/12/SWCC-10-12-Summary-Report.pdf
- Arquivo: https://github.com/NatLabRockies/turbine-models/blob/e9e4ccc6a87f50c0c65d236154a2897e752c47c9/turbine_models/data/Distributed/BergeyExcel10_8.9kW_7.csv; revisão: e9e4ccc6a87f50c0c65d236154a2897e752c47c9; SHA blob 26a6612097118cd03278726aa45d2d07d583818a.
- CSV: `config/wind_curves/BergeyExcel10_8.9kW_7.csv`; SHA-256 `794d45b30da9ae3745a46a37fda0e2256a8673262a8592f09805752932ad90b3`; domínio [0.5, 20.5]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: 8.863; erro relativo 0.41573034%; filtro numérico 1%: True; aprovação: pending_primary_document.
- Qualidade: {'power_curve': 'archived_table_pending_primary_verification', 'cut_in': 'secondary_archive', 'cut_out': 'not_provided', 'rated_wind_speed': 'secondary_archive', 'reference_density': 'not_provided'}; fronteira elétrica: {'quantity': 'archived_net_electrical_exchange', 'measurement_point': None, 'measurement_point_label': 'Fronteira exata pendente de documento primário', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': None, 'confidence': 'secondary_archive_only'}.
- Limitações: Somente análise da curva arquivada: relatório primário/variante e densidade não verificados; integração energética bloqueada. Valores negativos preservados como importação líquida observada, sem inferir o consumo interno total.

## Bergey Excel 15
- Identidade: Bergey / Excel 15; variante: None. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 15.6 kW; definição: `{'kind': 'archive_reference_at_wind_speed', 'wind_speed_mps': 11.0, 'relative_tolerance': 0.01, 'verification_status': 'pending_primary_document'}`. Pico 20.611 kW; 32 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 9.6 m; área 72.38229473870884 m²; altura selecionada None; opções []. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 2.5 m/s; cut-out None; re-cut-in None. rho None kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida -0.029 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: LPP-16-05-2019-Summary-Report.pdf; páginas PDF []; SHA documento None.
- Referência/versão: NREL/NatLabRockies e9e4ccc6a87f50c0c65d236154a2897e752c47c9; http://smallwindcertification.org/wp-content/uploads/2019/06/LPP-16-05-2019-Summary-Report.pdf
- Fonte primária: http://smallwindcertification.org/wp-content/uploads/2019/06/LPP-16-05-2019-Summary-Report.pdf
- Arquivo: https://github.com/NatLabRockies/turbine-models/blob/e9e4ccc6a87f50c0c65d236154a2897e752c47c9/turbine_models/data/Distributed/BergeyExcel15_15.6kW_9.6.csv; revisão: e9e4ccc6a87f50c0c65d236154a2897e752c47c9; SHA blob be89d146525221f0d13d1c0eb665783e8c7735ac.
- CSV: `config/wind_curves/BergeyExcel15_15.6kW_9.6.csv`; SHA-256 `d5eb6ccf68ba9de4e30fd01dd5bb481c097eb141ca1c04d94d58707176d82cc5`; domínio [1.0, 16.47]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: 15.5898; erro relativo 0.06538462%; filtro numérico 1%: True; aprovação: pending_primary_document.
- Qualidade: {'power_curve': 'archived_table_pending_primary_verification', 'cut_in': 'secondary_archive', 'cut_out': 'not_provided', 'rated_wind_speed': 'secondary_archive', 'reference_density': 'not_provided'}; fronteira elétrica: {'quantity': 'archived_net_electrical_exchange', 'measurement_point': None, 'measurement_point_label': 'Fronteira exata pendente de documento primário', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': None, 'confidence': 'secondary_archive_only'}.
- Limitações: Somente análise da curva arquivada: relatório primário/variante e densidade não verificados; integração energética bloqueada. Valores negativos preservados como importação líquida observada, sem inferir o consumo interno total.

## Kestrel e400nb
- Identidade: Kestrel (fabricante legal não confirmado) / e400nb; variante: None. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 2.5 kW; definição: `{'kind': 'archive_reference_at_wind_speed', 'wind_speed_mps': 11.0, 'relative_tolerance': 0.01, 'verification_status': 'pending_primary_document'}`. Pico 3.025 kW; 39 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 4 m; área 12.566370614359172 m²; altura selecionada None; opções []. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 4 m/s; cut-out None; re-cut-in None. rho None kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida -0.001 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: Summary-Report-10-16-2020.pdf; páginas PDF []; SHA documento None.
- Referência/versão: NREL/NatLabRockies e9e4ccc6a87f50c0c65d236154a2897e752c47c9; http://smallwindcertification.org/wp-content/uploads/2020/04/Summary-Report-10-16-2020.pdf
- Fonte primária: http://smallwindcertification.org/wp-content/uploads/2020/04/Summary-Report-10-16-2020.pdf
- Arquivo: https://github.com/NatLabRockies/turbine-models/blob/e9e4ccc6a87f50c0c65d236154a2897e752c47c9/turbine_models/data/Distributed/Kestrele400nb_2.5kW_4.csv; revisão: e9e4ccc6a87f50c0c65d236154a2897e752c47c9; SHA blob 3eddcb6ea68c9c2ddc7595f3b203a0136950aa2e.
- CSV: `config/wind_curves/Kestrele400nb_2.5kW_4.csv`; SHA-256 `4f6f8be33910a653e2ba115cd27865ce7a1b4ca9462da51bea1a522dc48fcfc5`; domínio [0.59, 19.49]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: 2.54216; erro relativo 1.68640000%; filtro numérico 1%: False; aprovação: pending_primary_document.
- Qualidade: {'power_curve': 'archived_table_pending_primary_verification', 'cut_in': 'secondary_archive', 'cut_out': 'not_provided', 'rated_wind_speed': 'secondary_archive', 'reference_density': 'not_provided'}; fronteira elétrica: {'quantity': 'archived_net_electrical_exchange', 'measurement_point': None, 'measurement_point_label': 'Fronteira exata pendente de documento primário', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': None, 'confidence': 'secondary_archive_only'}.
- Limitações: Somente análise da curva arquivada: relatório primário/variante e densidade não verificados; integração energética bloqueada. Valores negativos preservados como importação líquida observada, sem inferir o consumo interno total.

## SWIFT
- Identidade: Não confirmado (arquivo SWIFT) / SWIFT; variante: None. Não se aceita equivalência por potência ou diâmetro apenas.
- Referência: 1 kW; definição: `{'kind': 'archive_reference_at_wind_speed', 'wind_speed_mps': 11.0, 'relative_tolerance': 0.01, 'verification_status': 'pending_primary_document'}`. Pico 1.43 kW; 48 pontos originais, distribuição e Cp nos CSV (não reamostrados).
- Diâmetro 2.1 m; área 3.463605900582747 m²; altura selecionada None; opções []. Área dos pequenos é πD²/4 derivada de diâmetro secundário, não área ensaiada confirmada.
- Cut-in 3.4 m/s; cut-out None; re-cut-in None. rho None kg/m³. Nos pequenos cut-in é somente metadado secundário, não recorta bins de análise.
- Potência mínima líquida -0.01 kW. Auxiliares: observações negativas preservadas como importação líquida na análise; nenhuma inferência de consumo interno total.
- Documento: 56499.pdf; páginas PDF []; SHA documento None.
- Referência/versão: NREL/NatLabRockies e9e4ccc6a87f50c0c65d236154a2897e752c47c9; https://www.nrel.gov/docs/fy13osti/56499.pdf
- Fonte primária: https://www.nrel.gov/docs/fy13osti/56499.pdf
- Arquivo: https://github.com/NatLabRockies/turbine-models/blob/e9e4ccc6a87f50c0c65d236154a2897e752c47c9/turbine_models/data/Distributed/SWIFT_1kW_2.1.csv; revisão: e9e4ccc6a87f50c0c65d236154a2897e752c47c9; SHA blob 03cfa498ca79d76ed9aff60a681ea3abbdb4a210.
- CSV: `config/wind_curves/SWIFT_1kW_2.1.csv`; SHA-256 `d151168e38e2798f60bcc0689610c8fc5e43257361409df4bf5d8d03e2705d57`; domínio [0.54, 23.99]; nenhum cut-out inferido do último nó.
- P interpolada na velocidade de referência: 0.9023529411764706; erro relativo 9.76470588%; filtro numérico 1%: False; aprovação: pending_primary_document.
- Qualidade: {'power_curve': 'archived_table_pending_primary_verification', 'cut_in': 'secondary_archive', 'cut_out': 'not_provided', 'rated_wind_speed': 'secondary_archive', 'reference_density': 'not_provided'}; fronteira elétrica: {'quantity': 'archived_net_electrical_exchange', 'measurement_point': None, 'measurement_point_label': 'Fronteira exata pendente de documento primário', 'internal_turbine_losses_reapplied': False, 'downstream_grid_losses_included': None, 'confidence': 'secondary_archive_only'}.
- Limitações: Somente análise da curva arquivada: relatório primário/variante e densidade não verificados; integração energética bloqueada. Valores negativos preservados como importação líquida observada, sem inferir o consumo interno total.

## Condições ainda não comprovadas dos quatro pequenos

Os informes SWCC-10-12, LPP-16-05-2019, SWCC-10-16-2020 e NREL/TP-5000-56499 são identificados pelas páginas arquivadas; download primário retornou 403 na rede atual. Fabricante legal/variante elétrica, densidade normalizada, incerteza, fronteira elétrica e parâmetros de ensaio NÃO foram confirmados. `None` conserva ausências; geometria e cut-in secundários não equivalem a certificação. Não foram inventadas páginas ou SHA dos documentos não obtidos.

O manual BWC EXCEL 10 + Powersync II fornecido (rev.2.0, abril/2014, p.5) declara nominal comercial 10 kW a 11,6 m/s, AWEA 8,9 kW a 11 m/s, rotor 7 m e cut-in 2,2 m/s; o arquivo secundário indica 2,5 m/s. Não foi demonstrada identidade de revisão/sistema elétrico entre manual e ensaio. Por isso 10 kW não substitui a referência de 8,9, e o cut-in conflitante não é usado para modificar bins. O manual diz ausência de cut-out e furling 16–18 m/s para sua configuração: isso NÃO autoriza estender o CSV nem transferir a política para uma variante não confirmada.

Para liberar simulação dos pequenos: obter os relatórios primários corretos, confirmar individualmente identidade e condições, resolver Kestrel e SWIFT a 11 m/s e divergências YAML/página/manual, documentar densidade/aplicabilidade e a contabilidade de importações no balanço. Não basta habilitar acesso à rede nem passar os testes numéricos. Não modificar EMS para ocultar importações.
