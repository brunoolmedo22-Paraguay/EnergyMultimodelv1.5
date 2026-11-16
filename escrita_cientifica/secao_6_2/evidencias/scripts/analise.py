import csv
H=0.25
def load(k):
    rows=list(csv.DictReader(open(f'txt/{k}_series.csv')))
    for r in rows:
        for c in r:
            if c not in ('ini_utc','ini_local'):
                r[c]=float(r[c]) if r[c] not in ('',None) else None
    return rows
def fr(k):
    try: return list(csv.DictReader(open(f'txt/{k}_fronteiras.csv')))
    except FileNotFoundError: return None
ponta=lambda r: '18:00'<=r['ini_local']<'21:00'
for k in ['C1','C2','C3','C4']:
    R=load(k)
    g=lambda c,f=lambda r:True: sum((r.get(c) or 0) for r in R if f(r))*H
    print(f'===== {k}')
    print(' demanda total %.4f | ponta %.4f | fora %.4f'%(g('dem_real'),g('dem_real',ponta),g('dem_real',lambda r: not ponta(r))))
    print(' import total %.4f | ponta %.4f | fora %.4f'%(g('imp'),g('imp',ponta),g('imp',lambda r: not ponta(r))))
    print(' PV total %.4f | ponta %.4f | vert %.4f'%(g('pv_total'),g('pv_total',ponta),g('vert_total')))
    if 'descarga' in R[0]:
        print(' descarga total %.4f | ponta %.4f | fora %.4f'%(g('descarga'),g('descarga',ponta),g('descarga',lambda r: not ponta(r))))
        print(' carga total %.4f | ponta %.4f | fora %.4f'%(g('carga'),g('carga',ponta),g('carga',lambda r: not ponta(r))))
    ct=sum(r['custo_int'] for r in R); cp=sum(r['custo_int'] for r in R if ponta(r))
    print(' custo total %.4f | ponta %.4f | fora %.4f'%(ct,cp,ct-cp))
    # custo recomputado = imp*tarifa*H
    print(' custo recomputado imp×tarifa %.4f; max|dif| %.2e'%(sum(r['imp']*r['tarifa']*H for r in R), max(abs(r['imp']*r['tarifa']*H-r['custo_int']) for r in R)))
    print(' balanço max |dem - (imp+pv+desc-carga)| %.2e'%max(abs(r['dem_real']-(r['imp']+(r.get('pv_total') or 0)+(r.get('descarga') or 0)-(r.get('carga') or 0))) for r in R))
    mx=max((r['imp'],r['ini_local']) for r in R); print(' max import %.3f at %s; min %.3f'%(mx[0],mx[1],min(r['imp'] for r in R)))
    if 'descarga' in R[0]:
        act=[(r['ini_local'],round(r['descarga'],4),round(r['carga'],4),round(r.get('pv_total') or 0,3),round(r['dem_real'],3),round(r['imp'],3)) for r in R if r['descarga']>1e-6 or r['carga']>1e-6]
        print(' intervalos ativos',len(act))
        for a in act: print('   ',a)
    if k in ('C2','C4'):
        m=min((r['dem_real']-r['pv_total'],r['ini_local']) for r in R); print(' min carga líquida',m)
        print(' PV>0 intervals', [r['ini_local'] for r in R if r['pv_total']>1e-9][:1], [r['ini_local'] for r in R if r['pv_total']>1e-9][-1:], 'max PV %.3f'%max(r['pv_total'] for r in R))
        print(' PV na ponta', [(r['ini_local'],round(r['pv_total'],3)) for r in R if ponta(r) and r['pv_total']>1e-9])
    F=fr(k)
    if F:
        E=[float(x['E_kWh']) for x in F]
        print(' E ini %.4f fim %.4f min %.4f max %.4f at %s'%(E[0],E[-1],min(E),max(E),F[E.index(max(E))]['local']))
        print(' E at 13:00 %.3f, 15:00 %.3f, 18:00 %.3f, 21:00 %.3f'%tuple(float([x for x in F if x['local']==h][0]['E_kWh']) for h in ['13:00','15:00','18:00','21:00']))
