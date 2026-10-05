function D = Dbat_eq14(n, bat)
%DBAT_EQ14 Modelo empirico de degradacao da bateria (Eq.14, Zhang et al.
%2025), em funcao do numero de ciclos acumulado n.
    p = bat.deg_param; T = bat.deg_T_K; n = max(n,0);
    D = bat.deg_scale*(p.D*exp(p.F+p.G/(T+p.H))*n^p.E + n^p.I + p.J);
end
