import json
from pathlib import Path

entries = []

# 桂林电子科技大学 4145010595
guet_code = "4145010595"
guet_entries = [
    ("https://pcportal.guet.edu.cn/", "unified_portal", "智慧校园/pcportal"),
    ("https://iw.guet.edu.cn/", "unified_portal", "校内主页"),
    ("https://www.guet.edu.cn/utsc/", "academic_department_website", "本科教育"),
    ("https://www.guet.edu.cn/gra/", "academic_department_website", "研究生教育"),
    ("https://www.guet.edu.cn/zs/", "academic_department_website", "招生信息网"),
    ("https://www.guet.edu.cn/yjszs/", "academic_department_website", "研究生招生"),
    ("https://jy.guet.edu.cn", "academic_department_website", "毕业生就业网"),
    ("https://www.guet.edu.cn/international/", "academic_department_website", "国际交流"),
    ("https://www.guet.edu.cn/gdkyc/", "academic_department_website", "科学研究"),
    ("https://www.guet.edu.cn/rsc/88/list.htm", "academic_department_website", "师资队伍"),
    ("https://www.guet.edu.cn/rsc/89/list.htm", "academic_department_website", "诚聘英才"),
    ("https://www.guet.edu.cn/pubinfo/", "academic_department_website", "信息公开"),
    ("http://mail.guet.edu.cn/", "academic_department_website", "邮箱登录"),
    ("https://v.guet.edu.cn/login", "academic_department_website", "校外VPN"),
    ("http://xb.guet.edu.cn", "academic_department_website", "学报"),
    ("https://legalization.guet.edu.cn", "academic_department_website", "软件正版化"),
    ("https://mz.guet.edu.cn/", "academic_department_website", "媒资库"),
]
for url, stype, desc in guet_entries:
    entries.append({
        "school_name": "桂林电子科技大学",
        "school_code": guet_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 兰州交通大学 4162010732
lzjtu_code = "4162010732"
lzjtu_entries = [
    ("https://ehall.lzjtu.edu.cn/", "unified_portal", "网上办事大厅/ehall"),
    ("http://eip.lzjtu.edu.cn/", "unified_portal", "EIP服务大厅"),
    ("http://jiaowu.lzjtu.edu.cn/bkpg", "academic_department_website", "本科教学审核评估"),
    ("https://zsb.lzjtu.edu.cn/", "academic_department_website", "本科生招生"),
    ("http://yjsc.lzjtu.edu.cn/", "academic_department_website", "研究生招生"),
    ("https://dia.lzjtu.edu.cn/", "academic_department_website", "留学生招生"),
    ("http://cjxy.lzjtu.edu.cn/", "academic_department_website", "成教招生"),
    ("https://jyzx.lzjtu.edu.cn/", "academic_department_website", "就业指导中心"),
    ("http://wjpt.lzjtu.edu.cn", "academic_department_website", "网教平台"),
    ("https://lib.lzjtu.edu.cn/", "academic_department_website", "图书情报"),
    ("http://xsc.lzjtu.edu.cn/jkxl", "academic_department_website", "学生健康心理"),
    ("https://mail.lzjtu.cn/", "academic_department_website", "教师邮箱"),
    ("http://mail.stu.lzjtu.edu.cn/", "academic_department_website", "学生邮箱"),
    ("http://news.lzjtu.edu.cn", "academic_department_website", "新闻中心"),
    ("http://faculty.lzjtu.edu.cn/", "academic_department_website", "教师主页"),
    ("https://journal.lzjtu.edu.cn/", "academic_department_website", "交大学报"),
    ("https://cgzx.lzjtu.edu.cn/", "academic_department_website", "成果转化"),
    ("https://rcgz.lzjtu.edu.cn/", "academic_department_website", "人才招聘"),
    ("https://xxgk.lzjtu.edu.cn/", "academic_department_website", "信息公开"),
    ("https://en.lzjtu.edu.cn/", "academic_department_website", "English"),
    ("http://cxcy.lzjtu.edu.cn/", "academic_department_website", "创新创业"),
    ("https://edata.lzjtu.edu.cn/", "academic_department_website", "数据平台"),
    ("https://aichat.lzjtu.edu.cn/", "academic_department_website", "智能机器人"),
    ("http://tdjs.lzjtu.edu.cn/", "academic_department_website", "高职生教育"),
]
for url, stype, desc in lzjtu_entries:
    entries.append({
        "school_name": "兰州交通大学",
        "school_code": lzjtu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_148.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  桂林电子科技大学: {len(guet_entries)}")
print(f"  兰州交通大学: {len(lzjtu_entries)}")