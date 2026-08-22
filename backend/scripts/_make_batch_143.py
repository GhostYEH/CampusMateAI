import json
from pathlib import Path

entries = []

# 贵州大学 4152010657
gzu_code = "4152010657"
gzu_entries = [
    ("https://i.gzu.edu.cn", "unified_portal", "信息门户"),
    ("http://eol.gzu.edu.cn/", "unified_portal", "线上教学平台"),
    ("http://nae.gzu.edu.cn", "unified_portal", "非学历教育"),
    ("https://rso.gzu.edu.cn/", "academic_department_website", "本科招生"),
    ("https://gs.gzu.edu.cn/", "academic_department_website", "研究生招生"),
    ("https://cie.gzu.edu.cn/", "academic_department_website", "留学生招生"),
    ("http://hr.gzu.edu.cn", "academic_department_website", "人事处"),
    ("http://st.gzu.edu.cn/", "academic_department_website", "科技网"),
    ("http://hss.gzu.edu.cn/", "academic_department_website", "人文社科网"),
]
for url, stype, desc in gzu_entries:
    entries.append({
        "school_name": "贵州大学",
        "school_code": gzu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 山西大学 4114010108
sxu_code = "4114010108"
sxu_entries = [
    ("http://nehall.sxu.edu.cn/", "unified_portal", "数智山大/办事大厅"),
    ("http://jxjyxy.sxu.edu.cn/", "unified_portal", "继续教育"),
    ("https://sxu.yuketang.cn/", "unified_portal", "网络教学(雨课堂)"),
    ("http://bkzs.sxu.edu.cn/", "academic_department_website", "本科招生"),
    ("http://yjszsw.sxu.edu.cn/", "academic_department_website", "研究生招生"),
    ("http://siee.sxu.edu.cn/", "academic_department_website", "留学生招生"),
    ("http://job.sxu.edu.cn/", "academic_department_website", "就业"),
    ("http://rsc.sxu.edu.cn/", "academic_department_website", "招聘"),
    ("https://lib.sxu.edu.cn/", "academic_department_website", "图书馆"),
    ("http://xkjsbgs.sxu.edu.cn/", "academic_department_website", "学科建设"),
    ("http://gnhzc.sxu.edu.cn/", "academic_department_website", "校友会/国内合作"),
    ("http://infogk2.sxu.edu.cn/", "academic_department_website", "信息公开"),
    ("https://mets.sxu.edu.cn/", "academic_department_website", "VPN"),
    ("http://mail.sxu.edu.cn/", "academic_department_website", "教师邮箱"),
    ("https://dt.sxu.edu.cn/", "academic_department_website", "大同校区"),
]
for url, stype, desc in sxu_entries:
    entries.append({
        "school_name": "山西大学",
        "school_code": sxu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 广西大学 4145010593
gxu_code = "4145010593"
gxu_entries = [
    ("https://one.gxu.edu.cn", "unified_portal", "一件事门户"),
    ("http://bsdt.gxu.edu.cn", "unified_portal", "办事大厅"),
    ("http://jwc.gxu.edu.cn", "academic_department_website", "本科教务管理"),
    ("http://yjsc.gxu.edu.cn", "academic_department_website", "研究生管理"),
    ("http://cjxy.gxu.edu.cn/", "unified_portal", "继续教育"),
    ("http://zs.gxu.edu.cn/", "academic_department_website", "本科招生"),
    ("http://gjxy.gxu.edu.cn", "academic_department_website", "留学生招生"),
    ("http://jyy.gxu.edu.cn/", "academic_department_website", "就业指导"),
    ("http://kjc.gxu.edu.cn/", "academic_department_website", "科研管理"),
    ("http://cwc.gxu.edu.cn/", "academic_department_website", "财务"),
    ("http://prof.gxu.edu.cn/", "academic_department_website", "教师信息"),
    ("http://rszp.gxu.edu.cn/", "academic_department_website", "招聘"),
    ("https://mail.gxu.edu.cn/", "academic_department_website", "教工邮箱"),
    ("http://net.gxu.edu.cn/", "academic_department_website", "校园网"),
    ("https://vpn.gxu.edu.cn/", "academic_department_website", "VPN"),
    ("http://alumni.gxu.edu.cn/", "academic_department_website", "校友"),
    ("http://xbbj.gxu.edu.cn/", "academic_department_website", "学术期刊"),
    ("https://dwxwgk.gxu.edu.cn/", "academic_department_website", "信息公开"),
    ("http://hpc.gxu.edu.cn/", "academic_department_website", "超算平台"),
    ("http://pan.gxu.edu.cn/", "academic_department_website", "君武盘"),
    ("http://gxpt.gxu.edu.cn", "academic_department_website", "大型仪器共享"),
    ("https://fxcszx.gxu.edu.cn/", "academic_department_website", "分析测试中心"),
    ("https://xdxsg.gxu.edu.cn", "academic_department_website", "线上校史馆"),
    ("http://dxzx.gxu.edu.cn/", "academic_department_website", "党校在线"),
]
for url, stype, desc in gxu_entries:
    entries.append({
        "school_name": "广西大学",
        "school_code": gxu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_143.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  贵州大学: {len(gzu_entries)}")
print(f"  山西大学: {len(sxu_entries)}")
print(f"  广西大学: {len(gxu_entries)}")