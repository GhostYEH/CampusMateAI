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

nuc = "中北大学"
nuc_code = "4114010110"
add(nuc, nuc_code, "https://xmh.nuc.edu.cn", "unified_portal")
add(nuc, nuc_code, "https://atrust.nuc.edu.cn:10443/", "other")
add(nuc, nuc_code, "http://jwc.nuc.edu.cn/", "academic_department_website")
add(nuc, nuc_code, "http://grs.nuc.edu.cn/", "graduate_system")
add(nuc, nuc_code, "http://international.nuc.edu.cn/", "international_system")
add(nuc, nuc_code, "http://jxjy.nuc.edu.cn/", "continuing_education_system")
add(nuc, nuc_code, "https://std.nuc.edu.cn/", "research_system")
add(nuc, nuc_code, "https://fzgh.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://rlzyglc.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://zbzs.nuc.edu.cn/", "admission_website")
add(nuc, nuc_code, "http://zbjy.nuc.edu.cn/", "other")
add(nuc, nuc_code, "https://gnjlhzb.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://xyb.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://fund.nuc.edu.cn", "other")
add(nuc, nuc_code, "http://kjy.nuc.edu.cn/", "other")
add(nuc, nuc_code, "https://nuc.publish.founderss.cn/homeNav?lang=zh", "other")
add(nuc, nuc_code, "http://zbxxgk.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://library.nuc.edu.cn/page/934997/show", "other")
add(nuc, nuc_code, "https://zbcg.nuc.edu.cn/", "other")
add(nuc, nuc_code, "https://dxyq.nuc.edu.cn/build/#/web/apply/list", "other")
add(nuc, nuc_code, "http://nuc.fanya.chaoxing.com/portal", "other")
add(nuc, nuc_code, "http://hqfw.nuc.edu.cn/", "other")
add(nuc, nuc_code, "https://rlzyglc.nuc.edu.cn/", "other")
add(nuc, nuc_code, "https://xsxztjy.nuc.edu.cn/", "other")
add(nuc, nuc_code, "http://shpg.nuc.edu.cn", "other")

haut = "河南工业大学"
haut_code = "4141010463"
add(haut, haut_code, "https://portal.haut.edu.cn/portal-pc/index.html", "unified_portal")
add(haut, haut_code, "https://ehall.haut.edu.cn/main.html#/ServiceCenter", "unified_portal")
add(haut, haut_code, "http://oa.haut.edu.cn", "other")
add(haut, haut_code, "https://webmail.haut.edu.cn/", "other")
add(haut, haut_code, "https://vpn.haut.edu.cn/portal/#!/login", "other")
add(haut, haut_code, "http://zs.haut.edu.cn/", "admission_website")
add(haut, haut_code, "http://yjszs.haut.edu.cn", "admission_website")
add(haut, haut_code, "http://mba.haut.edu.cn", "admission_website")
add(haut, haut_code, "http://jxjy.haut.edu.cn/zxks/crxlzs.htm", "admission_website")
add(haut, haut_code, "https://sie.haut.edu.cn/index2.jsp?urltype=tree.TreeTempUrl&wbtreeid=1178", "admission_website")
add(haut, haut_code, "http://job.haut.edu.cn/", "other")
add(haut, haut_code, "http://sie.haut.edu.cn", "international_system")
add(haut, haut_code, "http://lib.haut.edu.cn", "other")
add(haut, haut_code, "https://lib.haut.edu.cn/", "other")
add(haut, haut_code, "https://dag.haut.edu.cn/zxfw.htm", "other")
add(haut, haut_code, "http://xxb.haut.edu.cn", "other")
add(haut, haut_code, "http://software.haut.edu.cn/", "other")
add(haut, haut_code, "http://zyzx.haut.edu.cn", "other")
add(haut, haut_code, "https://xgxt.haut.edu.cn/xsxt/sys/xggzptapp/*default/index.do", "other")
add(haut, haut_code, "https://xiaoyou.haut.edu.cn/", "other")
add(haut, haut_code, "https://mapp.haut.edu.cn/haut/", "other")
add(haut, haut_code, "http://old.haut.edu.cn", "other")
add(haut, haut_code, "https://dx.haut.edu.cn/pdy_wmw.jsp?urltype=tree.TreeTempUrl&wbtreeid=1006", "other")
add(haut, haut_code, "http://70.haut.edu.cn/", "other")
add(haut, haut_code, "https://chat.haut.edu.cn/ai-capability-center", "other")
add(haut, haut_code, "https://xb.haut.edu.cn/info/1046/1789.htm", "other")
add(haut, haut_code, "https://xuebaozk.haut.edu.cn/", "other")
add(haut, haut_code, "http://haut.ihwrm.com/", "other")
add(haut, haut_code, "https://jwc.haut.edu.cn/jxpg/pgsy.htm", "other")
add(haut, haut_code, "https://www.haut.edu.cn/ddhcs/", "other")

out = Path("data/discovery_batches/batch_153.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(entries)} entries to {out}")