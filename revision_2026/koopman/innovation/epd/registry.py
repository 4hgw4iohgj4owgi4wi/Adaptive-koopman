METHODS={
'EPD-K0-FL46':{'core':'frozen V-FL92-U8','geometry':'frozen FL output','role':'baseline'},
'EPD-K1-KIN':{'core':'bitwise K0 core','geometry':'kinematic','role':'zero-train physics'},
'EPD-K2-RES':{'core':'bitwise K0 core','geometry':'KIN+shared residual','role':'ablation'},
'EPD-K3-EQ':{'core':'bitwise K0 core','geometry':'KIN+equivariant residual','role':'ablation'},
'EPD-K4-EPD':{'core':'bitwise K0 core','geometry':'KIN+bounded shrunk equivariant residual','role':'candidate'},
'EPD-O1-KIN':{'input':'truth core','role':'oracle'},'EPD-O2-AX':{'input':'truth d/v','role':'oracle'}}

