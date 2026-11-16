import re,sys,csv
k=sys.argv[1]; src=sys.argv[2]; out=sys.argv[3]
rows=[];pg=0
pat=re.compile(r'^\s*(\d+)\s+(\d\d:\d\d)\s+(\d+)\s+(\d+)\s+(\w+)\s+([-\d.,]+)\s+([-\d.,]+)\s+([-\d.,—]+)\s+([-\d.,]+)\s+([-\d.,]+)\s+(\S+)')
for line in open(src):
    m=re.match(r'######## \S+ PÁGINA (\d+)',line)
    if m: pg=int(m.group(1)); continue
    m=pat.match(line)
    if m: rows.append([pg]+list(m.groups()))
def num(s):
    s=s.replace('.','').replace(',','.')
    try: return float(s)
    except: return None
with open(out,'w',newline='') as f:
    w=csv.writer(f); w.writerow(['pagina','j','tau','N','aplic','classe','objetivo','operativo','futuro','previsto_bloco','realizado_bloco','vf'])
    for r in rows: w.writerow(r)
print(k,len(rows),'linhas; páginas',sorted(set(r[0] for r in rows)))
