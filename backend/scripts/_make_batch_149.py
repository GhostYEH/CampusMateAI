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

sdust = "山东科技大学"
sdust_code = "4137010424"
add(sdust, sdust_code, "http://jwgl.sdust.edu.cn/", "edu_system")
add(sdust, sdust_code, "https://my.sdust.edu.cn/", "unified_portal")
add(sdust, sdust_code, "https://ehall.sdust.edu.cn", "unified_portal")
add(sdust, sdust_code, "https://jwc.sdust.edu.cn/", "academic_department_website")
add(sdust, sdust_code, "http://yjsy.sdust.edu.cn/", "graduate_system")
add(sdust, sdust_code, "http://cie.sdust.edu.cn/", "international_system")
add(sdust, sdust_code, "http://ccemanager.sdust.edu.cn/", "continuing_education_system")
add(sdust, sdust_code, "http://zs.sdust.edu.cn/", "admission_website")
add(sdust, sdust_code, "https://yjsy.sdust.edu.cn/zhaosheng/", "admission_website")
add(sdust, sdust_code, "http://cj.sdust.edu.cn/", "admission_website")
add(sdust, sdust_code, "http://keyan.sdust.edu.cn/", "research_system")
add(sdust, sdust_code, "http://rwskc.sdust.edu.cn/", "research_system")
add(sdust, sdust_code, "https://jszy.sdust.edu.cn/", "research_system")
add(sdust, sdust_code, "https://stiao.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://xkjs.sdust.edu.cn/", "other")
add(sdust, sdust_code, "http://fao.sdust.edu.cn/", "other")
add(sdust, sdust_code, "http://xy.sdust.edu.cn/", "other")
add(sdust, sdust_code, "http://jjh.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://news.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://xxgk.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://sklib.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://dangan.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://webvpn.sdust.edu.cn/", "other")
add(sdust, sdust_code, "http://oa.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://kyxt.sdust.edu.cn/userAction!do_casLogin.action", "research_system")
add(sdust, sdust_code, "https://sdust.fy.chaoxing.com/portal", "other")
add(sdust, sdust_code, "https://tech.sdust.edu.cn/wlfw.htm", "other")
add(sdust, sdust_code, "https://xb.sdust.edu.cn/index/tzgg.htm", "other")
add(sdust, sdust_code, "https://taxq.sdust.edu.cn/", "other")
add(sdust, sdust_code, "https://jnxq.sdust.edu.cn/", "other")

xaut = "西安理工大学"
xaut_code = "4161010700"
add(xaut, xaut_code, "http://jwgl.xaut.edu.cn/jsxsd/", "edu_system")
add(xaut, xaut_code, "https://ids.xaut.edu.cn/authserver/login", "unified_portal")
add(xaut, xaut_code, "https://mail.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://library.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://zhixing.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://webvpn.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://renshichu.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://renshichu.xaut.edu.cn/zpxx1/zpgg.htm", "other")
add(xaut, xaut_code, "http://zhaosheng.xaut.edu.cn/", "admission_website")
add(xaut, xaut_code, "http://yjsy.xaut.edu.cn/zsgz.htm", "admission_website")
add(xaut, xaut_code, "http://oice.xaut.edu.cn/lhlxs.htm", "international_system")
add(xaut, xaut_code, "http://sce.xaut.edu.cn/", "continuing_education_system")
add(xaut, xaut_code, "http://job.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://xyzh.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://efjjh.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://newoa.xaut.edu.cn:80", "other")
add(xaut, xaut_code, "http://xxgk.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://nic.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://hqfwc.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://yingxin.xaut.edu.cn/", "other")
add(xaut, xaut_code, "http://kjc.xaut.edu.cn/", "research_system")
add(xaut, xaut_code, "http://xuebao.xaut.edu.cn/xbdd.htm", "other")
add(xaut, xaut_code, "https://en.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://szw.xaut.edu.cn", "other")
add(xaut, xaut_code, "https://ddh.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://sqyr.xaut.edu.cn/", "other")
add(xaut, xaut_code, "https://jsjb.xaut.edu.cn/pc/mail/#/", "other")

henau = "河南农业大学"
henau_code = "4141010466"
add(henau, henau_code, "http://jw.henau.edu.cn/cas/login.action", "edu_system")
add(henau, henau_code, "http://i.henau.edu.cn/", "unified_portal")
add(henau, henau_code, "http://jwc.henau.edu.cn/", "academic_department_website")
add(henau, henau_code, "http://gra.henau.edu.cn/", "graduate_system")
add(henau, henau_code, "http://gj.henau.edu.cn/", "international_system")
add(henau, henau_code, "http://cj.henau.edu.cn/", "continuing_education_system")
add(henau, henau_code, "http://stud.henau.edu.cn/", "other")
add(henau, henau_code, "http://zs.henau.edu.cn/index.html", "admission_website")
add(henau, henau_code, "http://job.henau.edu.cn/", "other")
add(henau, henau_code, "http://kjc.henau.edu.cn/", "research_system")
add(henau, henau_code, "https://qkzx.henau.edu.cn/", "other")
add(henau, henau_code, "http://rs.henau.edu.cn/", "other")
add(henau, henau_code, "http://lib.henau.edu.cn/", "other")
add(henau, henau_code, "http://archives.henau.edu.cn/", "other")
add(henau, henau_code, "http://xyh.henau.edu.cn/", "other")
add(henau, henau_code, "https://jjh.henau.edu.cn/", "other")
add(henau, henau_code, "http://tw.henau.edu.cn/", "other")
add(henau, henau_code, "http://gonghui.henau.edu.cn/", "other")
add(henau, henau_code, "http://mail.henau.edu.cn/", "other")
add(henau, henau_code, "http://en.henau.edu.cn/", "other")
add(henau, henau_code, "https://gjc.henau.edu.cn/", "international_system")
add(henau, henau_code, "https://xczxyjy.henau.edu.cn/", "research_system")
add(henau, henau_code, "http://inrd.henau.edu.cn", "research_system")
add(henau, henau_code, "http://kjhzglb.henau.edu.cn/", "research_system")
add(henau, henau_code, "https://mek.henau.edu.cn/", "other")

out = Path("data/discovery_batches/batch_149.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(entries)} entries to {out}")