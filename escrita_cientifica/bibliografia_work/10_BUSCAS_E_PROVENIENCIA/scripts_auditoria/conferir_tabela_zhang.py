import ast,json,re,pathlib
root=pathlib.Path('repo_snapshot/models/battery_model.py')
tree=ast.parse(root.read_text());arrays={}
for n in tree.body:
 if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id.startswith('RC_'):
  ex=n.value;factor=1
  if isinstance(ex,ast.BinOp) and isinstance(ex.op,ast.Mult):factor=ast.literal_eval(ex.right);ex=ex.left
  if isinstance(ex,ast.Call) and isinstance(ex.func,ast.Attribute) and ex.func.attr=='array':arrays[n.targets[0].id]=[v*factor for v in ast.literal_eval(ex.args[0])]
text=pathlib.Path('research/texts/zhang.txt').read_text();part=text[text.index('Table 3. The polarization resistance'):];part=part[:part.index('3. Model Simulation')]
rows=[]
for line in part.splitlines():
 nums=re.findall(r'(?<!\S)\d+(?:\.\d+)?(?=\s|$)',line)
 if len(nums)!=7:continue
 soc,tau1,r1,c1,tau2,r2,c2=map(float,nums)
 if soc not in arrays['RC_SOC']:continue
 i=arrays['RC_SOC'].index(soc);c1*=1000;c2*=10000
 match=all(abs(v-arrays[k][i])<1e-10 for v,k in [(r1,'RC_R1'),(c1,'RC_C1'),(r2,'RC_R2'),(c2,'RC_C2')])
 rows.append({'soc':soc,'tau1_publicado_s':tau1,'r1_ohm':r1,'c1_F':c1,'tau1_rc_s':r1*c1,'tau2_publicado_s':tau2,'r2_ohm':r2,'c2_F':c2,'tau2_rc_s':r2*c2,'erro_rel_tau2':abs(tau2-r2*c2)/tau2,'quatro_parametros_codigo_iguais_tabela':match})
assert len(rows)==13
pathlib.Path('research/zhang_comparison.json').write_text(json.dumps(rows,indent=2))
print({'rows':len(rows),'matching':sum(r['quatro_parametros_codigo_iguais_tabela'] for r in rows),'inconsistency':[r for r in rows if r['erro_rel_tau2']>.05]})
