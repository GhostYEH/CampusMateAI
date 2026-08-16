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

sdutcm = "山东中医药大学"
sdutcm_code = "4137010441"
add(sdutcm, sdutcm_code, "https://jwc.sdutcm.edu.cn/", "academic_department_website")
add(sdutcm, sdutcm_code, "https://yjs.sdutcm.edu.cn/", "graduate_system")
add(sdutcm, sdutcm_code, "https://gjjiaoyu.sdutcm.edu.cn/", "international_system")
add(sdutcm, sdutcm_code, "https://sso.sdutcm.edu.cn/", "unified_portal")
add(sdutcm, sdutcm_code, "https://renshichu.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://renshichu.sdutcm.edu.cn/rcgz/rczp.htm", "other")
add(sdutcm, sdutcm_code, "https://kycx.sdutcm.edu.cn/", "research_system")
add(sdutcm, sdutcm_code, "https://cgzyzh.sdutcm.edu.cn/", "research_system")
add(sdutcm, sdutcm_code, "https://tcmlab.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://sdxb.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://sdzz.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://xxgk.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "http://sdutcm.ihwrm.com/", "other")
add(sdutcm, sdutcm_code, "https://yqgx.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "http://mail.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://lib.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://sdutcm.sdbys.com/", "other")
add(sdutcm, sdutcm_code, "http://zsc.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://xyh1.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://hqjj.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://sfpt.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://ddh.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "http://ztjy.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://dsxx.sdutcm.edu.cn/", "other")
add(sdutcm, sdutcm_code, "https://bwcx.sdutcm.edu.cn/", "other")

hbut = "湖北工业大学"
hbut_code = "4142010500"
add(hbut, hbut_code, "https://e.hbut.edu.cn/", "unified_portal")
add(hbut, hbut_code, "https://dean.hbut.edu.cn/", "academic_department_website")
add(hbut, hbut_code, "https://yjs.hbut.edu.cn/", "graduate_system")
add(hbut, hbut_code, "https://sie.hbut.edu.cn/", "international_system")
add(hbut, hbut_code, "https://ce.hbut.edu.cn/", "continuing_education_system")
add(hbut, hbut_code, "https://kjcy.hbut.edu.cn/", "research_system")
add(hbut, hbut_code, "https://rs.hbut.edu.cn/rczp.htm", "other")
add(hbut, hbut_code, "https://rs.hbut.edu.cn/bsh/zdjj.htm", "other")
add(hbut, hbut_code, "https://zs.hbut.edu.cn/", "admission_website")
add(hbut, hbut_code, "https://hbut.91wllm.cn/", "other")
add(hbut, hbut_code, "https://hbutyjs.91wllm.cn/", "other")
add(hbut, hbut_code, "https://dir.hbut.edu.cn/index.htm", "international_system")
add(hbut, hbut_code, "https://xyh.hbut.edu.cn/", "other")
add(hbut, hbut_code, "https://lib.hbut.edu.cn/", "other")
add(hbut, hbut_code, "https://museum.hbut.edu.cn/xsg/index.html", "other")
add(hbut, hbut_code, "http://news.hbut.edu.cn/", "other")
add(hbut, hbut_code, "https://xmail.hbut.edu.cn/", "other")
add(hbut, hbut_code, "http://en.hbut.edu.cn/", "other")
add(hbut, hbut_code, "https://xxgk.hbut.edu.cn/", "other")
add(hbut, hbut_code, "https://tend.hbut.edu.cn/index.chtml", "other")
add(hbut, hbut_code, "https://dag.hbut.edu.cn/", "other")

sicau = "四川农业大学"
sicau_code = "4151010626"
add(sicau, sicau_code, "https://jiaowu.sicau.edu.cn/", "academic_department_website")
add(sicau, sicau_code, "https://yan.sicau.edu.cn/", "graduate_system")
add(sicau, sicau_code, "https://ywtb.sicau.edu.cn/", "unified_portal")
add(sicau, sicau_code, "https://ecology.sicau.edu.cn", "other")
add(sicau, sicau_code, "https://webvpn.sicau.edu.cn", "other")
add(sicau, sicau_code, "https://zs.sicau.edu.cn/", "admission_website")
add(sicau, sicau_code, "https://job.sicau.edu.cn/", "other")
add(sicau, sicau_code, "http://ghc.sicau.edu.cn/", "international_system")
add(sicau, sicau_code, "http://nfy.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://rsc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://rsc.sicau.edu.cn/rczp.htm", "other")
add(sicau, sicau_code, "https://kjc.sicau.edu.cn/", "research_system")
add(sicau, sicau_code, "https://lib.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://dag.sicau.edu.cn", "other")
add(sicau, sicau_code, "https://ietc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://mail.sicau.edu.cn/", "other")
add(sicau, sicau_code, "http://mail.stu.sicau.edu.cn", "other")
add(sicau, sicau_code, "https://op.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://labshare.sicau.edu.cn/Portals/Home/Index", "other")
add(sicau, sicau_code, "https://vrs.sicau.edu.cn/", "other")
add(sicau, sicau_code, "http://news.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://xyh.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://xsc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://zjc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://cwc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://bwc.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://tw.sicau.edu.cn/", "other")
add(sicau, sicau_code, "https://xgh.sicau.edu.cn/", "other")
add(sicau, sicau_code, "http://www.cnzx.info/", "continuing_education_system")
add(sicau, sicau_code, "https://ic.sicau.edu.cn/", "other")

out = Path("data/discovery_batches/batch_151.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(entries)} entries to {out}")