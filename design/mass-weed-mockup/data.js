/* MASS WEED — inventory data (cannabis reframe of ME item catalog) */
window.MW_GLYPHS = {
  flower:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2c-1 5-5 7-5 11a5 5 0 0 0 10 0c0-4-4-6-5-11z"/><path d="M12 8v12"/></svg>',
  preroll: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 15l14-4 4 1-1 4-14 4z"/><path d="M17 11l-1 4"/></svg>',
  conc:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 3h8M9 3v5l-4 9a3 3 0 0 0 3 4h8a3 3 0 0 0 3-4l-4-9V3"/></svg>',
  vape:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="9" y="3" width="6" height="18" rx="2"/><path d="M9 8h6"/></svg>',
  edible:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="8" width="16" height="11" rx="2"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/></svg>',
  tinc:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 2h4v5l3 6a4 4 0 0 1-4 6h-2a4 4 0 0 1-4-6l3-6z"/></svg>'
};

window.MW_CATS = [
  { id:'flower',  label:'Flower',      glyph:'flower'  },
  { id:'preroll', label:'Pre-Roll',    glyph:'preroll' },
  { id:'conc',    label:'Concentrate', glyph:'conc'    },
  { id:'vape',    label:'Vape',        glyph:'vape'    },
  { id:'edible',  label:'Edible',      glyph:'edible'  },
  { id:'tinc',    label:'Tincture',    glyph:'tinc'    }
];

// stat schema per category — [name, unit, max]
window.MW_STATS = {
  flower:  [['THC Potency','%',35],['CBD Content','%',25],['Terpene Load','%',5],['Cure Quality','',100]],
  preroll: [['THC Potency','%',35],['Burn Rate','s',300],['Grind Consistency','',100],['Fill Weight','g',2]],
  conc:    [['THC Potency','%',95],['Terpene Load','%',15],['Purity','',100],['Yield','g',20]],
  vape:    [['THC Potency','%',90],['Airflow Rating','',100],['Puff Count','',400],['Battery Life','%',100]],
  edible:  [['THC per Dose','mg',100],['Onset Time','min',90],['Shelf Life','d',180],['Consistency','',100]],
  tinc:    [['THC Potency','mg/ml',60],['CBD Content','mg/ml',60],['Absorption','',100],['Shelf Life','d',365]]
};

// cultivators = ME "manufacturers"
// rarity: common | uncommon | rare | epic
function mk(cat, name, brand, rarity, s){ return {cat,name,brand,rarity,stats:s}; }

window.MW_ITEMS = {
  flower: [
    mk('flower','Blue Dream IX','Serrice Cultivars','rare',    [28,12,3.4,92]),
    mk('flower','OG Kush VIII','Elkoss Botanicals','uncommon', [24,8,2.9,84]),
    mk('flower','Gelato VIII','Ariake Genetics','rare',        [31,6,4.1,88]),
    mk('flower','Northern Lights VII','Haliat Farms','common', [19,14,2.2,78]),
    mk('flower','Sour Diesel VIII','Elanus Growworks','common',[22,5,3.0,80]),
    mk('flower','Wedding Cake IX','Ariake Genetics','epic',    [33,4,4.6,95]),
    mk('flower','Purple Haze VII','Elkoss Botanicals','common',[18,11,2.6,74])
  ],
  preroll: [
    mk('preroll','Infused Kush V','Elanus Growworks','uncommon',[27,240,88,1.5]),
    mk('preroll','Daily Diesel IV','Haliat Farms','common',     [20,180,72,1.0]),
    mk('preroll','Dogwalker VI','Serrice Cultivars','rare',     [30,300,94,1.2]),
    mk('preroll','Trainwreck IV','Elkoss Botanicals','common',  [21,210,70,1.0]),
    mk('preroll','Hash Hole IX','Ariake Genetics','epic',       [38,290,96,1.8])
  ],
  conc: [
    mk('conc','Live Resin IX','Ariake Genetics','epic',    [86,12,97,14]),
    mk('conc','Cured Rosin VIII','Serrice Cultivars','rare',[79,9,94,11]),
    mk('conc','Shatter VII','Elkoss Botanicals','common',   [72,4,88,9]),
    mk('conc','Diamonds IX','Haliat Farms','rare',          [92,6,95,8]),
    mk('conc','Budder VI','Elanus Growworks','uncommon',    [76,7,90,10])
  ],
  vape: [
    mk('vape','Distillate Cart IX','Ariake Genetics','rare',   [88,84,320,90]),
    mk('vape','Live Rosin Pod VIII','Serrice Cultivars','epic',[82,92,360,95]),
    mk('vape','Full Spectrum VI','Elkoss Botanicals','common', [74,70,240,80]),
    mk('vape','CO2 Cart V','Haliat Farms','common',            [70,66,220,78])
  ],
  edible: [
    mk('edible','Nano Gummy X','Serrice Cultivars','rare',   [10,18,120,96]),
    mk('edible','Dark Choc VIII','Ariake Genetics','uncommon',[25,55,150,90]),
    mk('edible','Fruit Chew VI','Elkoss Botanicals','common', [5,70,90,84]),
    mk('edible','Micro Mint IX','Elanus Growworks','epic',    [2,35,180,98])
  ],
  tinc: [
    mk('tinc','Sublingual IX','Serrice Cultivars','rare',    [40,40,92,300]),
    mk('tinc','Balanced 1:1 VIII','Ariake Genetics','uncommon',[30,30,88,270]),
    mk('tinc','MCT Base VI','Haliat Farms','common',          [25,10,80,240]),
    mk('tinc','Full Plant X','Elanus Growworks','epic',       [55,25,95,365])
  ]
};

// harvest recovered on intake (screenshot 1 reframe)
window.MW_RECOVERED = [
  { cat:'flower',  name:'Hurricane VIII',  brand:'Elanus Growworks', rarity:'common' },
  { cat:'preroll', name:'Avenger VIII',    brand:'Elkoss Botanicals',rarity:'common' },
  { cat:'conc',    name:'Reaper VIII',     brand:'Elkoss Botanicals',rarity:'rare'   },
  { cat:'edible',  name:'Duelist VIII',    brand:'Elanus Growworks', rarity:'rare'   },
  { cat:'vape',    name:'Tempest IX',      brand:'Ariake Genetics',  rarity:'epic'   },
  { cat:'tinc',    name:'Solace VII',      brand:'Serrice Cultivars',rarity:'uncommon'}
];
