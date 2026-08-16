import json
from pathlib import Path

entries = []

def add(school, code, url, stype, source="webfetch_official"):
    entries.append({
        "school_name": school,
        "school_code": code,
        "candidate_url": url,
        "system_type": stype,
        "source": source,
    })

qdu = "青岛大学"
qdu_code = "4137011065"
add(qdu, qdu_code, "https://ehall.qdu.edu.cn/new/index.html", "unified_portal")
add(qdu, qdu_code, "http://jwc.qdu.edu.cn", "academic_department_website")
add(qdu, qdu_code, "http://grad.qdu.edu.cn/", "graduate_system")
add(qdu, qdu_code, "https://cie.qdu.edu.cn/", "international_system")
add(qdu, qdu_code, "http://qucec.qdu.edu.cn/", "continuing_education_system")
add(qdu, qdu_code, "http://cxcy.qdu.edu.cn/", "other")
add(qdu, qdu_code, "http://zs.qdu.edu.cn/", "admission_website")
add(qdu, qdu_code, "https://grad.qdu.edu.cn/yzb/", "admission_website")
add(qdu, qdu_code, "http://istudy.qdu.edu.cn/cn/index", "admission_website")
add(qdu, qdu_code, "https://kjc.qdu.edu.cn", "research_system")
add(qdu, qdu_code, "https://rwskc.qdu.edu.cn/", "research_system")
add(qdu, qdu_code, "https://qks.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://tto.qdu.edu.cn/", "research_system")
add(qdu, qdu_code, "https://international.qdu.edu.cn/", "international_system")
add(qdu, qdu_code, "http://fwqd.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://alumni.qdu.edu.cn/", "other")
add(qdu, qdu_code, "http://shjm.qdu.edu.cn", "other")
add(qdu, qdu_code, "https://news.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://rlzy.qdu.edu.cn/szdw.htm", "other")
add(qdu, qdu_code, "https://rlzy.qdu.edu.cn/rczp.htm", "other")
add(qdu, qdu_code, "https://dag.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://webvpn.qdu.edu.cn", "other")
add(qdu, qdu_code, "https://oa.qdu.edu.cn/", "other")
add(qdu, qdu_code, "http://dflt.qdu.edu.cn", "other")
add(qdu, qdu_code, "https://cg.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://xxgk.qdu.edu.cn/", "other")
add(qdu, qdu_code, "http://yqgx.qdu.edu.cn", "other")
add(qdu, qdu_code, "http://lib.qdu.edu.cn", "other")
add(qdu, qdu_code, "https://houqin.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://mail.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://jsjb.sdei.edu.cn/", "other")
add(qdu, qdu_code, "http://youth.qdu.edu.cn/", "other")
add(qdu, qdu_code, "https://school.gxjy.sdei.edu.cn/qdu", "other")

ujn = "济南大学"
ujn_code = "4137010427"
add(ujn, ujn_code, "https://jwc.ujn.edu.cn/", "academic_department_website")
add(ujn, ujn_code, "https://yjs.ujn.edu.cn/", "graduate_system")
add(ujn, ujn_code, "https://siee.ujn.edu.cn/", "international_system")
add(ujn, ujn_code, "https://sce.ujn.edu.cn/", "continuing_education_system")
add(ujn, ujn_code, "http://course.ujn.edu.cn/portal", "other")
add(ujn, ujn_code, "https://stinfo.ujn.edu.cn/", "research_system")
add(ujn, ujn_code, "https://skc.ujn.edu.cn/", "research_system")
add(ujn, ujn_code, "https://xkc.ujn.edu.cn/", "other")
add(ujn, ujn_code, "http://t-transfer.ujn.edu.cn/", "research_system")
add(ujn, ujn_code, "http://admission.ujn.edu.cn/", "admission_website")
add(ujn, ujn_code, "http://yz.ujn.edu.cn/", "admission_website")
add(ujn, ujn_code, "http://isao.ujn.edu.cn/", "admission_website")
add(ujn, ujn_code, "http://sqa.ujn.edu.cn/", "admission_website")
add(ujn, ujn_code, "https://school.gxjy.sdei.edu.cn/ujn", "other")
add(ujn, ujn_code, "http://co-develop.ujn.edu.cn/", "other")
add(ujn, ujn_code, "https://iec.ujn.edu.cn/", "international_system")
add(ujn, ujn_code, "https://portal.ujn.edu.cn/", "unified_portal")
add(ujn, ujn_code, "http://xzxx.ujn.edu.cn/", "other")
add(ujn, ujn_code, "http://psy.ujn.edu.cn/", "other")
add(ujn, ujn_code, "http://library.ujn.edu.cn/", "other")
add(ujn, ujn_code, "https://rsc.ujn.edu.cn/rczp.htm", "other")
add(ujn, ujn_code, "https://xxgk.ujn.edu.cn/", "other")
add(ujn, ujn_code, "http://sygz.ujn.edu.cn/", "other")
add(ujn, ujn_code, "http://jndxb.ujn.edu.cn/", "other")
add(ujn, ujn_code, "https://jdda.ujn.edu.cn/", "other")
add(ujn, ujn_code, "https://www.ujn.edu.cn/jndxen", "other")

ytu = "烟台大学"
ytu_code = "4137011066"
add(ytu, ytu_code, "https://jwc.ytu.edu.cn/", "academic_department_website")
add(ytu, ytu_code, "https://yjs.ytu.edu.cn/index.htm", "graduate_system")
add(ytu, ytu_code, "https://ies.ytu.edu.cn", "international_system")
add(ytu, ytu_code, "https://jxjy.ytu.edu.cn", "continuing_education_system")
add(ytu, ytu_code, "https://stu.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://youth.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://kjc.ytu.edu.cn/", "research_system")
add(ytu, ytu_code, "http://skc.ytu.edu.cn/", "research_system")
add(ytu, ytu_code, "https://rso.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://gjc.ytu.edu.cn/", "international_system")
add(ytu, ytu_code, "https://rsc.ytu.edu.cn/index/zpxx.htm", "other")
add(ytu, ytu_code, "https://bkzs.ytu.edu.cn/", "admission_website")
add(ytu, ytu_code, "https://yjs.ytu.edu.cn/zsgz.htm", "admission_website")
add(ytu, ytu_code, "https://sie.ytu.edu.cn/", "admission_website")
add(ytu, ytu_code, "https://school.gxjy.sdei.edu.cn/ytu", "other")
add(ytu, ytu_code, "https://liuxuekorea.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://cas.ytu.edu.cn/lyuapServer/login", "unified_portal")
add(ytu, ytu_code, "http://oa.ytu.edu.cn/seeyon/ssologin.jsp", "other")
add(ytu, ytu_code, "https://www.lib.ytu.edu.cn", "other")
add(ytu, ytu_code, "https://zcc.ytu.edu.cn/zfcgzx/zbgg.htm", "other")
add(ytu, ytu_code, "http://xiaoyou.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://jyfzjjh.ytu.edu.cn", "other")
add(ytu, ytu_code, "https://gk.ytu.edu.cn/", "other")
add(ytu, ytu_code, "https://web.ytu.edu.cn/sqfw/", "other")

out = Path("data/discovery_batches/batch_150.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(entries)} entries to {out}")