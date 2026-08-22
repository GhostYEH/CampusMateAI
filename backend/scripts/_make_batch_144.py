import json
from pathlib import Path

entries = []

# 河北工程大学 4113010076
hebeu_code = "4113010076"
hebeu_entries = [
    ("https://jwglxxfwpt.hebeu.edu.cn/", "undergraduate-main", "综合教务系统服务平台"),
    ("https://portal.hebeu.edu.cn/", "unified_portal", "融合门户"),
    ("https://bsdt.hebeu.edu.cn/", "unified_portal", "一网通办/办事大厅"),
    ("https://jiaowu.hebeu.edu.cn/", "academic_department_website", "本专科教育/教务处"),
    ("https://yanjs.hebeu.edu.cn/", "academic_department_website", "研究生教育"),
    ("https://chengjiao.hebeu.edu.cn/", "academic_department_website", "继续教育"),
    ("http://zhaosheng.hebeu.edu.cn/", "academic_department_website", "本科招生"),
    ("http://jiuye.hebeu.edu.cn", "academic_department_website", "就业信息"),
    ("http://international.hebeu.edu.cn/", "academic_department_website", "留学生教育"),
    ("https://keyan.hebeu.edu.cn", "academic_department_website", "科研信息"),
    ("https://library.hebeu.edu.cn/", "academic_department_website", "图书馆"),
    ("https://xuebao.hebeu.edu.cn/", "academic_department_website", "学术刊物"),
    ("http://oa.hebeu.edu.cn/", "academic_department_website", "网上办公OA"),
    ("http://mail.hebeu.edu.cn/", "academic_department_website", "电子邮箱"),
    ("http://jiaofei.hebeu.edu.cn/xysf/", "academic_department_website", "缴费平台"),
    ("https://svpn.hebeu.edu.cn/", "academic_department_website", "VPN"),
    ("http://jswm.hebeu.edu.cn/", "academic_department_website", "军民融合"),
]
for url, stype, desc in hebeu_entries:
    entries.append({
        "school_name": "河北工程大学",
        "school_code": hebeu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 安徽理工大学 4134010361
aust_code = "4134010361"
aust_entries = [
    ("https://service.aust.edu.cn/EIP/nonlogin/homePage.htm", "unified_portal", "服务大厅"),
    ("http://jwc.aust.edu.cn/", "academic_department_website", "本科生教育/教务处"),
    ("http://yjsc.aust.edu.cn/", "academic_department_website", "研究生教育"),
    ("http://jxjy.aust.edu.cn/", "academic_department_website", "继续教育"),
    ("http://zs.aust.edu.cn/", "academic_department_website", "本科招生网"),
    ("http://yjszs.aust.edu.cn/", "academic_department_website", "研究生招生网"),
    ("http://aust.ahbys.com/", "academic_department_website", "就业信息网"),
    ("https://rsc.aust.edu.cn/", "academic_department_website", "师资队伍/人事"),
    ("https://fgc.aust.edu.cn/", "academic_department_website", "学科建设"),
    ("https://kyb.aust.edu.cn/", "academic_department_website", "科研部"),
    ("https://tsg.aust.edu.cn/", "academic_department_website", "图书资源"),
    ("http://wsb.aust.edu.cn/", "academic_department_website", "国际学院"),
    ("https://news.aust.edu.cn/", "academic_department_website", "新闻网"),
    ("https://xxgk.aust.edu.cn/", "academic_department_website", "信息公开"),
    ("http://oa.aust.edu.cn/login.shtml", "academic_department_website", "电子政务OA"),
    ("https://mail.aust.edu.cn", "academic_department_website", "邮箱登录"),
]
for url, stype, desc in aust_entries:
    entries.append({
        "school_name": "安徽理工大学",
        "school_code": aust_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 福建师范大学 4135010394
fjnu_code = "4135010394"
fjnu_entries = [
    ("https://jwglxt.fjnu.edu.cn/", "undergraduate-main", "正方教学管理系统"),
    ("http://jwc.fjnu.edu.cn", "academic_department_website", "本科生教育/教务处"),
    ("http://yjsy.fjnu.edu.cn", "academic_department_website", "研究生教育/研究生院"),
    ("http://zsb.fjnu.edu.cn", "academic_department_website", "本科生招生"),
    ("http://career.fjnu.edu.cn/", "academic_department_website", "就业指导中心"),
    ("http://wjzy.fjnu.edu.cn/", "academic_department_website", "继续教育/网络教育"),
    ("http://kjc.fjnu.edu.cn", "academic_department_website", "科学技术研究"),
    ("http://skc.fjnu.edu.cn", "academic_department_website", "社会科学研究"),
    ("http://xuebao.fjnu.edu.cn/", "academic_department_website", "学报编辑部"),
    ("http://xxgk.fjnu.edu.cn", "academic_department_website", "信息公开"),
    ("http://xyzh.fjnu.edu.cn", "academic_department_website", "校友会"),
    ("http://oice.fjnu.edu.cn/", "academic_department_website", "国际合作与交流处"),
    ("https://xywksh.fjnu.edu.cn/xqksh/", "unified_portal", "数字校情"),
    ("https://oa.fjnu.edu.cn", "academic_department_website", "OA系统"),
    ("http://library.fjnu.edu.cn/", "academic_department_website", "图书馆"),
    ("http://mail.fjnu.edu.cn", "academic_department_website", "邮件系统"),
    ("http://rsc.fjnu.edu.cn/", "academic_department_website", "人事处"),
    ("http://cwc.fjnu.edu.cn", "academic_department_website", "财务处"),
    ("http://youth.fjnu.edu.cn", "academic_department_website", "校团委"),
]
for url, stype, desc in fjnu_entries:
    entries.append({
        "school_name": "福建师范大学",
        "school_code": fjnu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_144.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  河北工程大学: {len(hebeu_entries)}")
print(f"  安徽理工大学: {len(aust_entries)}")
print(f"  福建师范大学: {len(fjnu_entries)}")