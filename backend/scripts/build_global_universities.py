#!/usr/bin/env python3
"""Build global_universities.json by merging existing QS/THE data with
a comprehensive hand-curated list of major research universities worldwide.

Run from backend/:
    python scripts/build_global_universities.py
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Existing ranked data ──────────────────────────────────────────────
def load_existing() -> dict[str, dict]:
    """Load QS + THE, keyed by lowercase domain."""
    merged: dict[str, dict] = {}
    for fname in ("the_global_top200.json", "qs_global_top300.json"):
        path = DATA_DIR / fname
        if path.exists():
            for s in json.loads(path.read_text()):
                d = s["domain"].lower().strip()
                if d not in merged:
                    merged[d] = s
    return merged


# ── Additional universities (not in QS top 300 / THE top 200) ────────
# Format: (name, domain, country_code)
ADDITIONAL: list[tuple[str, str, str]] = [
    # ── United States (fill to ~100 total) ────────────────────────────
    ("Vanderbilt University", "vanderbilt.edu", "US"),
    ("University of Rochester", "rochester.edu", "US"),
    ("Case Western Reserve University", "case.edu", "US"),
    ("Tulane University", "tulane.edu", "US"),
    ("University of Virginia", "virginia.edu", "US"),
    ("University of Notre Dame", "nd.edu", "US"),
    ("Georgetown University", "georgetown.edu", "US"),
    ("Wake Forest University", "wfu.edu", "US"),
    ("Tufts University", "tufts.edu", "US"),
    ("Rensselaer Polytechnic Institute", "rpi.edu", "US"),
    ("Lehigh University", "lehigh.edu", "US"),
    ("Northeastern University", "northeastern.edu", "US"),
    ("Brandeis University", "brandeis.edu", "US"),
    ("University of Colorado Boulder", "colorado.edu", "US"),
    ("University of Oregon", "uoregon.edu", "US"),
    ("University of Connecticut", "uconn.edu", "US"),
    ("University of Iowa", "uiowa.edu", "US"),
    ("University of Kansas", "ku.edu", "US"),
    ("University of Kentucky", "uky.edu", "US"),
    ("Iowa State University", "iastate.edu", "US"),
    ("Oregon State University", "oregonstate.edu", "US"),
    ("Colorado State University", "colostate.edu", "US"),
    ("University of Nebraska-Lincoln", "unl.edu", "US"),
    ("University of Oklahoma", "ou.edu", "US"),
    ("University of South Carolina", "sc.edu", "US"),
    ("University of Tennessee", "utk.edu", "US"),
    ("University of Delaware", "udel.edu", "US"),
    ("University of New Mexico", "unm.edu", "US"),
    ("George Mason University", "gmu.edu", "US"),
    ("Drexel University", "drexel.edu", "US"),
    ("Stevens Institute of Technology", "stevens.edu", "US"),
    ("Illinois Institute of Technology", "iit.edu", "US"),
    ("Worcester Polytechnic Institute", "wpi.edu", "US"),
    ("Clarkson University", "clarkson.edu", "US"),
    ("Santa Clara University", "scu.edu", "US"),
    ("University of Hawaii at Manoa", "hawaii.edu", "US"),
    ("University of Vermont", "uvm.edu", "US"),
    ("Florida International University", "fiu.edu", "US"),
    ("San Diego State University", "sdsu.edu", "US"),

    # ── Canada (fill to ~30) ──────────────────────────────────────────
    ("Simon Fraser University", "sfu.ca", "CA"),
    ("University of Victoria", "uvic.ca", "CA"),
    ("York University", "yorku.ca", "CA"),
    ("Concordia University", "concordia.ca", "CA"),
    ("Carleton University", "carleton.ca", "CA"),
    ("Dalhousie University", "dal.ca", "CA"),
    ("University of Manitoba", "umanitoba.ca", "CA"),
    ("University of Saskatchewan", "usask.ca", "CA"),
    ("Memorial University of Newfoundland", "mun.ca", "CA"),
    ("University of Regina", "uregina.ca", "CA"),
    ("Université Laval", "ulaval.ca", "CA"),
    ("University of New Brunswick", "unb.ca", "CA"),
    ("Ryerson University (Toronto Metropolitan University)", "torontomu.ca", "CA"),
    ("University of Windsor", "uwindsor.ca", "CA"),
    ("University of Guelph", "uoguelph.ca", "CA"),

    # ── United Kingdom (fill to ~50) ──────────────────────────────────
    ("University of Bath", "bath.ac.uk", "UK"),
    ("University of Exeter", "exeter.ac.uk", "UK"),
    ("Lancaster University", "lancaster.ac.uk", "UK"),
    ("University of York", "york.ac.uk", "UK"),
    ("University of Surrey", "surrey.ac.uk", "UK"),
    ("Loughborough University", "lboro.ac.uk", "UK"),
    ("University of Leicester", "le.ac.uk", "UK"),
    ("University of Sussex", "sussex.ac.uk", "UK"),
    ("University of East Anglia", "uea.ac.uk", "UK"),
    ("Royal Holloway University of London", "royalholloway.ac.uk", "UK"),
    ("University of Strathclyde", "strath.ac.uk", "UK"),
    ("Heriot-Watt University", "hw.ac.uk", "UK"),
    ("University of Dundee", "dundee.ac.uk", "UK"),
    ("University of Stirling", "stir.ac.uk", "UK"),
    ("Swansea University", "swansea.ac.uk", "UK"),
    ("Brunel University London", "brunel.ac.uk", "UK"),
    ("Aston University", "aston.ac.uk", "UK"),
    ("University of Kent", "kent.ac.uk", "UK"),
    ("University of Essex", "essex.ac.uk", "UK"),
    ("Aberystwyth University", "aber.ac.uk", "UK"),
    ("City, University of London", "city.ac.uk", "UK"),
    ("Birkbeck, University of London", "bbk.ac.uk", "UK"),

    # ── Germany (fill to ~40) ─────────────────────────────────────────
    ("University of Stuttgart", "uni-stuttgart.de", "DE"),
    ("University of Hamburg", "uni-hamburg.de", "DE"),
    ("University of Cologne", "uni-koeln.de", "DE"),
    ("University of Bonn", "uni-bonn.de", "DE"),
    ("University of Frankfurt", "uni-frankfurt.de", "DE"),
    ("Dresden University of Technology", "tu-dresden.de", "DE"),
    ("University of Duisburg-Essen", "uni-due.de", "DE"),
    ("University of Würzburg", "uni-wuerzburg.de", "DE"),
    ("University of Jena", "uni-jena.de", "DE"),
    ("University of Leipzig", "uni-leipzig.de", "DE"),
    ("University of Kiel", "uni-kiel.de", "DE"),
    ("University of Bremen", "uni-bremen.de", "DE"),
    ("University of Mannheim", "uni-mannheim.de", "DE"),
    ("University of Konstanz", "uni-konstanz.de", "DE"),
    ("University of Regensburg", "uni-regensburg.de", "DE"),
    ("University of Ulm", "uni-ulm.de", "DE"),
    ("Technische Universität Darmstadt", "tu-darmstadt.de", "DE"),
    ("Technische Universität Braunschweig", "tu-braunschweig.de", "DE"),
    ("Karlsruhe Institute of Technology", "kit.edu", "DE"),
    ("Leibniz University Hannover", "uni-hannover.de", "DE"),
    ("University of Marburg", "uni-marburg.de", "DE"),
    ("University of Bayreuth", "uni-bayreuth.de", "DE"),
    ("University of Giessen", "uni-giessen.de", "DE"),
    ("University of Potsdam", "uni-potsdam.de", "DE"),

    # ── France (fill to ~30) ──────────────────────────────────────────
    ("Sorbonne University", "sorbonne-universite.fr", "FR"),
    ("University of Strasbourg", "unistra.fr", "FR"),
    ("University of Bordeaux", "u-bordeaux.fr", "FR"),
    ("University of Lyon 1", "univ-lyon1.fr", "FR"),
    ("University of Montpellier", "umontpellier.fr", "FR"),
    ("University of Toulouse III", "univ-tlse3.fr", "FR"),
    ("University of Aix-Marseille", "univ-amu.fr", "FR"),
    ("University of Grenoble Alpes", "univ-grenoble-alpes.fr", "FR"),
    ("University of Lille", "univ-lille.fr", "FR"),
    ("University of Nantes", "univ-nantes.fr", "FR"),
    ("University of Rennes 1", "univ-rennes1.fr", "FR"),
    ("University of Nice Sophia Antipolis", "univ-cotedazur.fr", "FR"),
    ("CentraleSupélec", "centralesupelec.fr", "FR"),
    ("INSA Lyon", "insa-lyon.fr", "FR"),
    ("Mines ParisTech", "minesparis.psl.eu", "FR"),
    ("ENSTA Paris", "ensta-paris.fr", "FR"),

    # ── Netherlands ───────────────────────────────────────────────────
    ("Vrije Universiteit Amsterdam", "vu.nl", "NL"),
    ("Radboud University", "ru.nl", "NL"),
    ("Tilburg University", "tilburguniversity.edu", "NL"),
    ("University of Groningen", "rug.nl", "NL"),
    ("Maastricht University", "maastrichtuniversity.nl", "NL"),
    ("University of Twente", "utwente.nl", "NL"),
    ("Wageningen University", "wur.nl", "NL"),
    ("Erasmus University Rotterdam", "eur.nl", "NL"),
    ("Leiden University", "universiteitleiden.nl", "NL"),

    # ── Switzerland ───────────────────────────────────────────────────
    ("University of Basel", "unibas.ch", "CH"),
    ("University of Bern", "unibe.ch", "CH"),
    ("University of Geneva", "unige.ch", "CH"),
    ("University of Lausanne", "unil.ch", "CH"),
    ("University of St. Gallen", "unisg.ch", "CH"),
    ("University of Fribourg", "unifr.ch", "CH"),
    ("University of Neuchâtel", "unine.ch", "CH"),
    ("Università della Svizzera italiana", "usi.ch", "CH"),

    # ── Scandinavia ───────────────────────────────────────────────────
    ("Chalmers University of Technology", "chalmers.se", "SE"),
    ("Stockholm University", "su.se", "SE"),
    ("Uppsala University", "uu.se", "SE"),
    ("Linköping University", "liu.se", "SE"),
    ("University of Gothenburg", "gu.se", "SE"),
    ("Umeå University", "umu.se", "SE"),
    ("Aalborg University", "aau.dk", "DK"),
    ("University of Southern Denmark", "sdu.dk", "DK"),
    ("Aarhus University", "au.dk", "DK"),
    ("Norwegian University of Science and Technology", "ntnu.no", "NO"),
    ("University of Bergen", "uib.no", "NO"),
    ("University of Tromsø", "uit.no", "NO"),
    ("University of Turku", "utu.fi", "FI"),
    ("University of Tampere", "tuni.fi", "FI"),
    ("University of Oulu", "oulu.fi", "FI"),
    ("University of Jyväskylä", "jyu.fi", "FI"),

    # ── Italy ─────────────────────────────────────────────────────────
    ("Sapienza University of Rome", "uniroma1.it", "IT"),
    ("University of Padova", "unipd.it", "IT"),
    ("University of Bologna", "unibo.it", "IT"),
    ("University of Pisa", "unipi.it", "IT"),
    ("University of Florence", "unifi.it", "IT"),
    ("University of Naples Federico II", "unina.it", "IT"),
    ("University of Turin", "unito.it", "IT"),
    ("University of Genova", "unige.it", "IT"),
    ("University of Trento", "unitn.it", "IT"),
    ("Scuola Normale Superiore", "sns.it", "IT"),
    ("SISSA Trieste", "sissa.it", "IT"),
    ("University of Trieste", "units.it", "IT"),
    ("Ca' Foscari University of Venice", "unive.it", "IT"),

    # ── Spain ─────────────────────────────────────────────────────────
    ("University of Barcelona", "ub.edu", "ES"),
    ("Autonomous University of Madrid", "uam.es", "ES"),
    ("Autonomous University of Barcelona", "uab.cat", "ES"),
    ("Complutense University of Madrid", "ucm.es", "ES"),
    ("University of Valencia", "uv.es", "ES"),
    ("University of Granada", "ugr.es", "ES"),
    ("University of Seville", "us.es", "ES"),
    ("Pompeu Fabra University", "upf.edu", "ES"),
    ("University of the Basque Country", "ehu.eus", "ES"),
    ("University of Salamanca", "usal.es", "ES"),
    ("University of Zaragoza", "unizar.es", "ES"),
    ("Carlos III University of Madrid", "uc3m.es", "ES"),

    # ── Other Europe ──────────────────────────────────────────────────
    ("University of Vienna", "univie.ac.at", "AT"),
    ("Graz University of Technology", "tugraz.at", "AT"),
    ("University of Innsbruck", "uibk.ac.at", "AT"),
    ("KU Leuven", "kuleuven.be", "BE"),
    ("Ghent University", "ugent.be", "BE"),
    ("Université libre de Bruxelles", "ulb.be", "BE"),
    ("Université catholique de Louvain", "uclouvain.be", "BE"),
    ("Trinity College Dublin", "tcd.ie", "IE"),
    ("University College Dublin", "ucd.ie", "IE"),
    ("National University of Ireland Galway", "universityofgalway.ie", "IE"),
    ("University of Lisbon", "ulisboa.pt", "PT"),
    ("University of Porto", "up.pt", "PT"),
    ("University of Coimbra", "uc.pt", "PT"),
    ("University of Warsaw", "uw.edu.pl", "PL"),
    ("Jagiellonian University", "uj.edu.pl", "PL"),
    ("Warsaw University of Technology", "pw.edu.pl", "PL"),
    ("AGH University of Science and Technology", "agh.edu.pl", "PL"),
    ("Charles University", "cuni.cz", "CZ"),
    ("Czech Technical University in Prague", "cvut.cz", "CZ"),
    ("University of Athens", "uoa.gr", "GR"),
    ("Aristotle University of Thessaloniki", "auth.gr", "GR"),
    ("National Technical University of Athens", "ntua.gr", "GR"),
    ("Eötvös Loránd University", "elte.hu", "HU"),
    ("Budapest University of Technology", "bme.hu", "HU"),
    ("University of Bucharest", "unibuc.ro", "RO"),
    ("Babeș-Bolyai University", "ubbcluj.ro", "RO"),
    ("University of Zagreb", "unizg.hr", "HR"),
    ("University of Ljubljana", "uni-lj.si", "SI"),
    ("University of Belgrade", "bg.ac.rs", "RS"),

    # ── China (fill to ~50) ───────────────────────────────────────────
    ("Nanjing University", "nju.edu.cn", "CN"),
    ("Wuhan University", "whu.edu.cn", "CN"),
    ("Sun Yat-sen University", "sysu.edu.cn", "CN"),
    ("Huazhong University of Science and Technology", "hust.edu.cn", "CN"),
    ("Xi'an Jiaotong University", "xjtu.edu.cn", "CN"),
    ("Harbin Institute of Technology", "hit.edu.cn", "CN"),
    ("Southeast University", "seu.edu.cn", "CN"),
    ("Tianjin University", "tju.edu.cn", "CN"),
    ("Sichuan University", "scu.edu.cn", "CN"),
    ("Dalian University of Technology", "dlut.edu.cn", "CN"),
    ("University of Science and Technology Beijing", "ustb.edu.cn", "CN"),
    ("Beijing Normal University", "bnu.edu.cn", "CN"),
    ("Xiamen University", "xmu.edu.cn", "CN"),
    ("Shandong University", "sdu.edu.cn", "CN"),
    ("Jilin University", "jlu.edu.cn", "CN"),
    ("Nankai University", "nankai.edu.cn", "CN"),
    ("Chongqing University", "cqu.edu.cn", "CN"),
    ("Lanzhou University", "lzu.edu.cn", "CN"),
    ("China Agricultural University", "cau.edu.cn", "CN"),
    ("East China Normal University", "ecnu.edu.cn", "CN"),
    ("Central South University", "csu.edu.cn", "CN"),
    ("Northwestern Polytechnical University", "nwpu.edu.cn", "CN"),
    ("Beijing Institute of Technology", "bit.edu.cn", "CN"),
    ("Renmin University of China", "ruc.edu.cn", "CN"),
    ("South China University of Technology", "scut.edu.cn", "CN"),
    ("University of Electronic Science and Technology of China", "uestc.edu.cn", "CN"),
    ("Ocean University of China", "ouc.edu.cn", "CN"),
    ("China University of Geosciences", "cug.edu.cn", "CN"),
    ("ShanghaiTech University", "shanghaitech.edu.cn", "CN"),
    ("Southern University of Science and Technology", "sustech.edu.cn", "CN"),
    ("Westlake University", "westlake.edu.cn", "CN"),

    # ── Japan (fill to ~30) ───────────────────────────────────────────
    ("Nagoya University", "nagoya-u.ac.jp", "JP"),
    ("Hokkaido University", "hokudai.ac.jp", "JP"),
    ("Hiroshima University", "hiroshima-u.ac.jp", "JP"),
    ("Kobe University", "kobe-u.ac.jp", "JP"),
    ("Okayama University", "okayama-u.ac.jp", "JP"),
    ("Kanazawa University", "kanazawa-u.ac.jp", "JP"),
    ("Chiba University", "chiba-u.ac.jp", "JP"),
    ("Niigata University", "niigata-u.ac.jp", "JP"),
    ("Kumamoto University", "kumamoto-u.ac.jp", "JP"),
    ("Keio University", "keio.ac.jp", "JP"),
    ("Waseda University", "waseda.jp", "JP"),
    ("Tokyo Institute of Technology", "titech.ac.jp", "JP"),
    ("Ritsumeikan University", "ritsumei.ac.jp", "JP"),
    ("Doshisha University", "doshisha.ac.jp", "JP"),
    ("Nagaoka University of Technology", "nagaokaut.ac.jp", "JP"),
    ("Japan Advanced Institute of Science and Technology", "jaist.ac.jp", "JP"),
    ("Nara Institute of Science and Technology", "naist.jp", "JP"),

    # ── South Korea (fill to ~20) ─────────────────────────────────────
    ("Hanyang University", "hanyang.ac.kr", "KR"),
    ("Kyung Hee University", "khu.ac.kr", "KR"),
    ("Chung-Ang University", "cau.ac.kr", "KR"),
    ("Inha University", "inha.ac.kr", "KR"),
    ("Sogang University", "sogang.ac.kr", "KR"),
    ("Ewha Womans University", "ewha.ac.kr", "KR"),
    ("Konkuk University", "konkuk.ac.kr", "KR"),
    ("Pusan National University", "pusan.ac.kr", "KR"),
    ("Kyungpook National University", "knu.ac.kr", "KR"),
    ("Chonnam National University", "jnu.ac.kr", "KR"),
    ("Ajou University", "ajou.ac.kr", "KR"),
    ("University of Seoul", "uos.ac.kr", "KR"),

    # ── Taiwan ────────────────────────────────────────────────────────
    ("National Cheng Kung University", "ncku.edu.tw", "TW"),
    ("National Tsing Hua University", "nthu.edu.tw", "TW"),
    ("National Chiao Tung University", "nycu.edu.tw", "TW"),
    ("National Central University", "ncu.edu.tw", "TW"),
    ("National Sun Yat-sen University", "nsysu.edu.tw", "TW"),
    ("National Chung Hsing University", "nchu.edu.tw", "TW"),
    ("Taipei Medical University", "tmu.edu.tw", "TW"),
    ("National Taiwan University of Science and Technology", "ntust.edu.tw", "TW"),
    ("National Taipei University of Technology", "ntut.edu.tw", "TW"),
    ("Academia Sinica", "sinica.edu.tw", "TW"),

    # ── India (fill to ~30) ───────────────────────────────────────────
    ("Indian Institute of Technology Delhi", "iitd.ac.in", "IN"),
    ("Indian Institute of Technology Kanpur", "iitk.ac.in", "IN"),
    ("Indian Institute of Technology Kharagpur", "iitkgp.ac.in", "IN"),
    ("Indian Institute of Technology Madras", "iitm.ac.in", "IN"),
    ("Indian Institute of Technology Roorkee", "iitr.ac.in", "IN"),
    ("Indian Institute of Technology Guwahati", "iitg.ac.in", "IN"),
    ("Indian Institute of Technology Hyderabad", "iith.ac.in", "IN"),
    ("Indian Institute of Science", "iisc.ac.in", "IN"),
    ("Jawaharlal Nehru University", "jnu.ac.in", "IN"),
    ("University of Delhi", "du.ac.in", "IN"),
    ("Jadavpur University", "jaduniv.edu.in", "IN"),
    ("Anna University", "annauniv.edu", "IN"),
    ("Birla Institute of Technology and Science", "bits-pilani.ac.in", "IN"),
    ("National Institute of Technology Tiruchirappalli", "nitt.edu", "IN"),
    ("Vellore Institute of Technology", "vit.ac.in", "IN"),
    ("Manipal Academy of Higher Education", "manipal.edu", "IN"),
    ("Tata Institute of Fundamental Research", "tifr.res.in", "IN"),
    ("Indian Statistical Institute", "isical.ac.in", "IN"),
    ("IIIT Hyderabad", "iiit.ac.in", "IN"),
    ("Indian Institute of Technology Indore", "iiti.ac.in", "IN"),

    # ── Australia (fill to ~20) ───────────────────────────────────────
    ("Macquarie University", "mq.edu.au", "AU"),
    ("University of Tasmania", "utas.edu.au", "AU"),
    ("Griffith University", "griffith.edu.au", "AU"),
    ("Deakin University", "deakin.edu.au", "AU"),
    ("RMIT University", "rmit.edu.au", "AU"),
    ("La Trobe University", "latrobe.edu.au", "AU"),
    ("Swinburne University of Technology", "swinburne.edu.au", "AU"),
    ("Flinders University", "flinders.edu.au", "AU"),
    ("James Cook University", "jcu.edu.au", "AU"),

    # ── New Zealand ───────────────────────────────────────────────────
    ("Victoria University of Wellington", "wgtn.ac.nz", "NZ"),
    ("University of Waikato", "waikato.ac.nz", "NZ"),
    ("Massey University", "massey.ac.nz", "NZ"),
    ("Lincoln University", "lincoln.ac.nz", "NZ"),

    # ── Southeast Asia ────────────────────────────────────────────────
    ("Chulalongkorn University", "chula.ac.th", "TH"),
    ("Mahidol University", "mahidol.ac.th", "TH"),
    ("Kasetsart University", "ku.ac.th", "TH"),
    ("Chiang Mai University", "cmu.ac.th", "TH"),
    ("King Mongkut's University of Technology Thonburi", "kmutt.ac.th", "TH"),
    ("University of Malaya", "um.edu.my", "MY"),
    ("Universiti Putra Malaysia", "upm.edu.my", "MY"),
    ("Universiti Sains Malaysia", "usm.my", "MY"),
    ("Universiti Kebangsaan Malaysia", "ukm.edu.my", "MY"),
    ("Universiti Teknologi Malaysia", "utm.my", "MY"),
    ("University of the Philippines Diliman", "upd.edu.ph", "PH"),
    ("Ateneo de Manila University", "ateneo.edu", "PH"),
    ("De La Salle University", "dlsu.edu.ph", "PH"),
    ("University of Indonesia", "ui.ac.id", "ID"),
    ("Bandung Institute of Technology", "itb.ac.id", "ID"),
    ("Gadjah Mada University", "ugm.ac.id", "ID"),
    ("Bogor Agricultural University", "ipb.ac.id", "ID"),
    ("Vietnam National University Hanoi", "vnu.edu.vn", "VN"),
    ("Vietnam National University Ho Chi Minh City", "vnuhcm.edu.vn", "VN"),
    ("Hanoi University of Science and Technology", "hust.edu.vn", "VN"),
    ("University of Colombo", "cmb.ac.lk", "LK"),

    # ── Middle East ───────────────────────────────────────────────────
    ("Tel Aviv University", "tau.ac.il", "IL"),
    ("Hebrew University of Jerusalem", "huji.ac.il", "IL"),
    ("Technion – Israel Institute of Technology", "technion.ac.il", "IL"),
    ("Weizmann Institute of Science", "weizmann.ac.il", "IL"),
    ("Ben-Gurion University of the Negev", "bgu.ac.il", "IL"),
    ("University of Haifa", "haifa.ac.il", "IL"),
    ("Bar-Ilan University", "biu.ac.il", "IL"),
    ("King Fahd University of Petroleum and Minerals", "kfupm.edu.sa", "SA"),
    ("King Abdullah University of Science and Technology", "kaust.edu.sa", "SA"),
    ("King Saud University", "ksu.edu.sa", "SA"),
    ("Khalifa University", "ku.ac.ae", "AE"),
    ("United Arab Emirates University", "uaeu.ac.ae", "AE"),
    ("Boğaziçi University", "boun.edu.tr", "TR"),
    ("Middle East Technical University", "metu.edu.tr", "TR"),
    ("Koç University", "ku.edu.tr", "TR"),
    ("Sabancı University", "sabanciuniv.edu", "TR"),
    ("Bilkent University", "bilkent.edu.tr", "TR"),
    ("Istanbul Technical University", "itu.edu.tr", "TR"),
    ("Hacettepe University", "hacettepe.edu.tr", "TR"),
    ("Ankara University", "ankara.edu.tr", "TR"),
    ("Sharif University of Technology", "sharif.edu", "IR"),
    ("University of Tehran", "ut.ac.ir", "IR"),
    ("Amirkabir University of Technology", "aut.ac.ir", "IR"),
    ("Iran University of Science and Technology", "iust.ac.ir", "IR"),
    ("Isfahan University of Technology", "iut.ac.ir", "IR"),
    ("Ferdowsi University of Mashhad", "um.ac.ir", "IR"),
    ("American University of Beirut", "aub.edu.lb", "LB"),
    ("University of Jordan", "ju.edu.jo", "JO"),
    ("Jordan University of Science and Technology", "just.edu.jo", "JO"),

    # ── Africa ────────────────────────────────────────────────────────
    ("University of Cape Town", "uct.ac.za", "ZA"),
    ("University of the Witwatersrand", "wits.ac.za", "ZA"),
    ("Stellenbosch University", "sun.ac.za", "ZA"),
    ("University of Pretoria", "up.ac.za", "ZA"),
    ("University of KwaZulu-Natal", "ukzn.ac.za", "ZA"),
    ("Rhodes University", "ru.ac.za", "ZA"),
    ("University of the Western Cape", "uwc.ac.za", "ZA"),
    ("Cairo University", "cu.edu.eg", "EG"),
    ("American University in Cairo", "aucegypt.edu", "EG"),
    ("Ain Shams University", "asu.edu.eg", "EG"),
    ("Alexandria University", "alexu.edu.eg", "EG"),
    ("University of Lagos", "unilag.edu.ng", "NG"),
    ("University of Ibadan", "ui.edu.ng", "NG"),
    ("Obafemi Awolowo University", "oauife.edu.ng", "NG"),
    ("Covenant University", "covenantuniversity.edu.ng", "NG"),
    ("University of Nairobi", "uonbi.ac.ke", "KE"),
    ("Kenyatta University", "ku.ac.ke", "KE"),
    ("University of Ghana", "ug.edu.gh", "GH"),
    ("Kwame Nkrumah University of Science and Technology", "knust.edu.gh", "GH"),
    ("Mohammed V University", "um5.ac.ma", "MA"),
    ("University of Tunis El Manar", "utm.rnu.tn", "TN"),
    ("Makerere University", "mak.ac.ug", "UG"),
    ("University of Dar es Salaam", "udsm.ac.tz", "TZ"),
    ("Addis Ababa University", "aau.edu.et", "ET"),

    # ── Latin America ─────────────────────────────────────────────────
    ("University of São Paulo", "usp.br", "BR"),
    ("University of Campinas", "unicamp.br", "BR"),
    ("Federal University of Rio de Janeiro", "ufrj.br", "BR"),
    ("Federal University of Minas Gerais", "ufmg.br", "BR"),
    ("Federal University of Rio Grande do Sul", "ufrgs.br", "BR"),
    ("São Paulo State University", "unesp.br", "BR"),
    ("Federal University of São Carlos", "ufscar.br", "BR"),
    ("Federal University of Santa Catarina", "ufsc.br", "BR"),
    ("Federal University of Paraná", "ufpr.br", "BR"),
    ("Pontifícia Universidade Católica do Rio de Janeiro", "puc-rio.br", "BR"),
    ("Federal University of Pernambuco", "ufpe.br", "BR"),
    ("Federal University of Bahia", "ufba.br", "BR"),
    ("National Autonomous University of Mexico", "unam.mx", "MX"),
    ("Monterrey Institute of Technology", "tec.mx", "MX"),
    ("Instituto Politécnico Nacional", "ipn.mx", "MX"),
    ("Universidad Autónoma Metropolitana", "uam.mx", "MX"),
    ("University of Guadalajara", "udg.mx", "MX"),
    ("CINVESTAV", "cinvestav.mx", "MX"),
    ("University of Buenos Aires", "uba.ar", "AR"),
    ("National University of Córdoba", "unc.edu.ar", "AR"),
    ("National University of La Plata", "unlp.edu.ar", "AR"),
    ("Instituto Balseiro", "ib.edu.ar", "AR"),
    ("Pontificia Universidad Católica de Chile", "uc.cl", "CL"),
    ("University of Chile", "uchile.cl", "CL"),
    ("Universidad de Concepción", "udec.cl", "CL"),
    ("Universidad Técnica Federico Santa María", "usm.cl", "CL"),
    ("Universidad de los Andes", "uniandes.edu.co", "CO"),
    ("Universidad Nacional de Colombia", "unal.edu.co", "CO"),
    ("Universidad del Valle", "univalle.edu.co", "CO"),

    # ── Russia & Central Asia ─────────────────────────────────────────
    ("Moscow State University", "msu.ru", "RU"),
    ("Saint Petersburg State University", "spbu.ru", "RU"),
    ("Novosibirsk State University", "nsu.ru", "RU"),
    ("Moscow Institute of Physics and Technology", "mipt.ru", "RU"),
    ("Bauman Moscow State Technical University", "bmstu.ru", "RU"),
    ("ITMO University", "itmo.ru", "RU"),
    ("HSE University", "hse.ru", "RU"),
    ("Tomsk State University", "tsu.ru", "RU"),
    ("Kazan Federal University", "kpfu.ru", "RU"),
    ("Peter the Great St. Petersburg Polytechnic University", "spbstu.ru", "RU"),
    ("Ural Federal University", "urfu.ru", "RU"),
    ("Nazarbayev University", "nu.edu.kz", "KZ"),
    ("Al-Farabi Kazakh National University", "kaznu.kz", "KZ"),
]


def main() -> None:
    existing = load_existing()
    print(f"Loaded {len(existing)} existing schools from QS/THE")

    # Start with existing schools (preserve their ranks)
    all_schools: dict[str, dict] = dict(existing)

    # Add new schools
    added = 0
    for name, domain, country in ADDITIONAL:
        d = domain.lower().strip()
        if d not in all_schools:
            all_schools[d] = {
                "rank": 0,  # will be assigned later
                "name": name,
                "domain": d,
                "country": country,
            }
            added += 1

    print(f"Added {added} new schools (total: {len(all_schools)})")

    # Sort: ranked schools first (by rank), then unranked alphabetically
    ranked = [s for s in all_schools.values() if s.get("rank", 0) > 0]
    unranked = [s for s in all_schools.values() if s.get("rank", 0) == 0]
    ranked.sort(key=lambda s: s["rank"])
    unranked.sort(key=lambda s: s["name"])

    # Re-assign continuous ranks
    result = []
    for i, s in enumerate(ranked + unranked, 1):
        result.append({
            "rank": i,
            "name": s["name"],
            "domain": s["domain"],
            "country": s["country"],
        })

    # Stats
    countries = sorted(set(s["country"] for s in result))
    print(f"Total: {len(result)} schools across {len(countries)} countries")
    print(f"Countries: {countries}")

    # Country distribution
    from collections import Counter
    dist = Counter(s["country"] for s in result)
    for c, n in dist.most_common():
        print(f"  {c}: {n}")

    # Write output
    out_path = DATA_DIR / "global_universities.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
