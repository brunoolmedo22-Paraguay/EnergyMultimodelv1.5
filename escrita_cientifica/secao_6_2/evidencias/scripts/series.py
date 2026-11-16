import sys, os, re, csv, json, glob
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))
from svgser import run, ymap
def xmap(xt):
    (p1,l1),(p2,l2)=xt[0],xt[-1]
    fmt=lambda l: datetime.strptime(l,'%d/%m/%Y %H:%M') if '/' in l else datetime.strptime('02/10/2026 '+l,'%d/%m/%Y %H:%M')
    t1=fmt(l1); t2=fmt(l2)
    return lambda px: t1+timedelta(seconds=(px-p1)*(t2-t1).total_seconds()/(p2-p1))
def rnd(t):  # arredonda ao minuto
    return (t+timedelta(seconds=30)).replace(second=0,microsecond=0)
def steps(line,ym,xm):
    out=[]
    for s in line['segs']:
        (x0,y0)=s[0]; (x1,y1)=s[1]
        out.append((rnd(xm(x0)),rnd(xm(x1)),ym(y0)))
    return out
def case(k):
    base=f'zips/{k}/figuras/svg/'
    f1=base+'01_demanda_potencia_por_recurso.svg'
    res,xt=run(f1); xm=xmap(xt)
    ser={}
    names={0:['dem_real','dem_prev','nao_atendida'],1:['imp','exp']}
    for i,a in enumerate(res):
        ym=ymap(a['yticks']); t=' '.join(a['title'])
        if 'Demanda [kW]' in t: nm=['dem_real','dem_prev','nao_atendida']
        elif 'PCC' in t: nm=['imp','exp']
        elif 'Bateria' in t: nm=['descarga','carga']
        elif 'Renov' in t: nm=[]; 
        elif 'PEMFC' in t: nm=['pemfc']
        else: nm=[]
        if 'Renov' in t:
            for j,l in enumerate(a['lines']):
                key=('pv_aprov' if j%2==0 else 'pv_vert')+f'_{j//2}'
                ser[key]=steps(l,ym,xm)
        else:
            for n,l in zip(nm,a['lines']): ser[n]=steps(l,ym,xm)
    return ser
def bat(k):
    fs=glob.glob(f'zips/{k}/figuras/svg/02_bateria_*.svg')
    if not fs: return None
    res,xt=run(fs[0]); xm=xmap(xt)
    out={}
    for a in res:
        ym=ymap(a['yticks']); t=' '.join(a['title'])
        l=a['lines'][0]; pts=[p for s in l['segs'] for p in s]
        out['E' if 'Energia' in t else 'SOC']=[(rnd(xm(x)),ym(y)) for x,y in pts]
    return out
def custo(k):
    fs=glob.glob(f'zips/{k}/figuras/svg/0*_tarifas_e_custo_realizado.svg')
    res,xt=run(fs[0]); xm=xmap(xt); out={}
    for a in res:
        ym=ymap(a['yticks']); t=' '.join(a['title'])
        if 'Tarifa' in t and a['lines']:
            out['tarifa']=steps(a['lines'][0],ym,xm)
        if 'Custo' in t:
            out['custo_int']=steps(a['lines'][0],ym,xm)
            pts=[p for s in a['lines'][1]['segs'] for p in s]
            out['custo_acum']=[(rnd(xm(x)),ym(y)) for x,y in pts]
    return out
if __name__=='__main__':
    allr={}
    for k in ['C1','C2','C3','C4','C5']:
        s=case(k); b=bat(k); c=custo(k)
        n=len(s['dem_real'])
        rows=[]
        for i in range(n):
            t0,t1,_=s['dem_real'][i]
            r={'k':i,'ini_utc':t0.strftime('%Y-%m-%d %H:%M'),'ini_local':(t0-timedelta(hours=3)).strftime('%H:%M')}
            for key,v in s.items():
                assert v[i][0]==t0, (k,key,i,v[i][0],t0)
                r[key]=v[i][2]
            pvk=[x for x in s if x.startswith('pv_aprov')]
            r['pv_total']=sum(s[x][i][2] for x in pvk) if pvk else None
            r['vert_total']=sum(s[x][i][2] for x in s if x.startswith('pv_vert')) if pvk else None
            if 'tarifa' in c: r['tarifa']=c['tarifa'][i][2]
            r['custo_int']=c['custo_int'][i][2]
            rows.append(r)
        cols=list(rows[0].keys())
        with open(f'txt/{k}_series.csv','w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
        if b:
            with open(f'txt/{k}_fronteiras.csv','w',newline='') as f:
                w=csv.writer(f); w.writerow(['fronteira','utc','local','E_kWh','SOC_pct'])
                for j,((t,e),(t2,sc)) in enumerate(zip(b['E'],b['SOC'])):
                    w.writerow([j,t.strftime('%Y-%m-%d %H:%M'),(t-timedelta(hours=3)).strftime('%H:%M'),e,sc])
        print(k,'intervalos',n,'cols',cols, 'fronteiras', len(b['E']) if b else None)
