import { EduRepository } from '../../repository/EduRepository';
import { EduScheduleItemDto, EduScheduleItemsResponse } from '../../data/ApiClient';
import { CampusPalette, lightPalette, darkPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { ApiClient } from '../../data/ApiClient';

const WEEKDAY_NAMES: string[] = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const COURSE_COLORS: number[] = [0xFF5B70ED, 0xFFF29A49, 0xFF37B89B, 0xFF9369E8, 0xFFE85B7A, 0xFF42A5F5, 0xFF66BB6A, 0xFFAB47BC];

interface DetailRow { label: string; value: string; }
interface ScheduleCard {
  id: string;
  item: EduScheduleItemDto;
  weekday: number;
  startSection: number;
  endSection: number;
  lane: number;
  laneCount: number;
  course_name: string;
  location: string;
  color: number;
}

const TIME_COLUMN_WIDTH: number = 48;
const DAY_COLUMN_WIDTH: number = 112;
const SECTION_HEIGHT: number = 72;
const HEADER_HEIGHT: number = 40;

function weeksContains(weeks: string | undefined, weekText: string | undefined, week: number): boolean {
  const w = weeks !== undefined ? weeks.trim() : '';
  if (w.length === 0) return true;
  if (weekText !== undefined && weekText.indexOf('单') >= 0 && week % 2 === 0) return false;
  if (weekText !== undefined && weekText.indexOf('双') >= 0 && week % 2 === 1) return false;
  const cleaned = w.replace(/周/g, '').replace(/ /g, '');
  const parts = cleaned.split(/[,，;；]/);
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i].trim();
    if (p.length === 0) continue;
    if (p.endsWith('单') && week % 2 === 0) continue;
    if (p.endsWith('双') && week % 2 === 1) continue;
    const core = p.replace(/单$/, '').replace(/双$/, '');
    if (core.indexOf('-') >= 0) {
      const range = core.split('-');
      if (range.length === 2) {
        const s = parseInt(range[0], 10);
        const e = parseInt(range[1], 10);
        if (!isNaN(s) && !isNaN(e) && week >= s && week <= e) return true;
      }
    } else {
      const n = parseInt(core, 10);
      if (!isNaN(n) && n === week) return true;
    }
  }
  return false;
}

function formatTeachers(teachers: string[] | undefined, teacher: string | undefined): string {
  if (teachers !== undefined && teachers.length > 0) {
    const filtered = teachers.filter((t: string) => t !== undefined && t.length > 0);
    if (filtered.length > 0) return filtered.join('、');
  }
  if (teacher !== undefined && teacher.length > 0) return teacher;
  return '';
}

function formatTime(weekday: number | undefined, start: number | undefined, end: number | undefined, startTime: string | undefined, endTime: string | undefined): string {
  if (weekday === undefined && start === undefined) return '';
  let sb = '';
  if (weekday !== undefined && weekday >= 1 && weekday <= 7) sb += WEEKDAY_NAMES[weekday - 1];
  if (start !== undefined) {
    sb += ' 第' + start;
    if (end !== undefined && end !== start) sb += '-' + end;
    sb += '节';
  }
  if ((startTime !== undefined && startTime.length > 0) || (endTime !== undefined && endTime.length > 0)) {
    sb += '\n' + (startTime || '') + (endTime !== undefined && endTime.length > 0 ? '-' + endTime : '');
  }
  return sb;
}

function formatWeeks(weeks: string | undefined, weekText: string | undefined): string {
  if (weekText !== undefined && weekText.length > 0) {
    return weeks !== undefined && weeks.length > 0 ? weekText + '（' + weeks + '）' : weekText;
  }
  return weeks || '';
}

function formatCredit(credit: number): string {
  return credit === Math.floor(credit) ? Math.floor(credit) + ' 学分' : credit + ' 学分';
}

function formatHours(hours: number): string {
  return hours === Math.floor(hours) ? Math.floor(hours).toString() : hours.toString();
}

function courseColorCode(item: EduScheduleItemDto): number {
  const key = (item.course_code || item.course_name || '');
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = ((hash << 5) - hash + key.charCodeAt(i)) & 0x7FFFFFFF;
  return COURSE_COLORS[hash % COURSE_COLORS.length];
}

function buildDetailRows(item: EduScheduleItemDto): DetailRow[] {
  const rows: DetailRow[] = [];
  const teachers = formatTeachers(item.teachers, item.teacher);
  if (teachers.length > 0) rows.push({ label: '教师', value: teachers });
  const time = formatTime(item.weekday, item.start_section, item.end_section, item.start_time, item.end_time);
  if (time.length > 0) rows.push({ label: '上课时间', value: time });
  if (item.location !== undefined && item.location.length > 0) rows.push({ label: '地点', value: item.location });
  const weeks = formatWeeks(item.weeks, item.week_text);
  if (weeks.length > 0) rows.push({ label: '周次', value: weeks });
  if (item.credit !== undefined) rows.push({ label: '学分', value: formatCredit(item.credit) });
  if (item.course_nature !== undefined && item.course_nature.length > 0) rows.push({ label: '课程性质', value: item.course_nature });
  if (item.course_category !== undefined && item.course_category.length > 0) rows.push({ label: '课程类别', value: item.course_category });
  if (item.course_type !== undefined && item.course_type.length > 0) rows.push({ label: '课程类型', value: item.course_type });
  if (item.teaching_class !== undefined && item.teaching_class.length > 0) rows.push({ label: '教学班', value: item.teaching_class });
  if (item.assessment_method !== undefined && item.assessment_method.length > 0) rows.push({ label: '考核方式', value: item.assessment_method });
  if (item.exam_type !== undefined && item.exam_type.length > 0) rows.push({ label: '考试类型', value: item.exam_type });
  if (item.college !== undefined && item.college.length > 0) rows.push({ label: '开课学院', value: item.college });
  if (item.department !== undefined && item.department.length > 0) rows.push({ label: '开课系', value: item.department });
  if (item.campus !== undefined && item.campus.length > 0) rows.push({ label: '校区', value: item.campus });
  if (item.class_name !== undefined && item.class_name.length > 0) rows.push({ label: '班级', value: item.class_name });
  if (item.total_hours !== undefined) rows.push({ label: '总学时', value: formatHours(item.total_hours) });
  if (item.theory_hours !== undefined) rows.push({ label: '理论学时', value: formatHours(item.theory_hours) });
  if (item.practice_hours !== undefined) rows.push({ label: '实践学时', value: formatHours(item.practice_hours) });
  if (item.language !== undefined && item.language.length > 0) rows.push({ label: '授课语言', value: item.language });
  if (item.semester !== undefined && item.semester.length > 0) rows.push({ label: '学期', value: item.semester });
  if (item.note !== undefined && item.note.length > 0) rows.push({ label: '备注', value: item.note });
  return rows;
}

function buildExtraRows(extraInfo: Record<string, Object> | undefined): DetailRow[] {
  if (extraInfo === undefined) return [];
  const rows: DetailRow[] = [];
  const keys = Object.keys(extraInfo);
  for (let i = 0; i < keys.length; i++) {
    const k = keys[i];
    const v = extraInfo[k];
    const vs = v !== undefined && v !== null ? String(v) : '';
    if (vs.length > 0) rows.push({ label: k, value: vs });
  }
  return rows;
}

@Component
export struct EduSchedulePage {
  @Prop darkMode: boolean = false;
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @State loading: boolean = true;
  @State currentWeek: number = 1;
  @State allItems: EduScheduleItemDto[] = [];
  @State scheduleCards: ScheduleCard[] = [];
  @State maxSection: number = 12;
  @State scheduleEmpty: boolean = false;
  @State sheetVisible: boolean = false;
  @State detailCourseName: string = '';
  @State detailCourseCode: string = '';
  @State detailRows: DetailRow[] = [];
  @State detailExtraRows: DetailRow[] = [];

  onBack: () => void = () => {};

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  buildClient(): ApiClient {
    return new ApiClient(this.apiBaseUrl, () => this.authToken, null);
  }

  async aboutToAppear() {
    await this.loadSchedule();
  }

  async loadSchedule() {
    this.loading = true;
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      const resp: EduScheduleItemsResponse = await repo.listScheduleItems(undefined);
      this.allItems = resp.items.filter((it: EduScheduleItemDto) => it.is_stale !== true);
    } catch (e) {
      this.allItems = [];
    } finally {
      this.loading = false;
       this.buildScheduleGrid();
    }
  }

  buildScheduleGrid() {
    const week = this.currentWeek;
    const filtered = this.allItems.filter((it: EduScheduleItemDto) => {
      return weeksContains(it.weeks, it.week_text, week)
        && it.weekday !== undefined && it.weekday >= 1 && it.weekday <= 7
        && it.start_section !== undefined && it.start_section >= 1;
    });
    let maxSection = 12;
    for (let i = 0; i < filtered.length; i++) {
      const end = filtered[i].end_section !== undefined && filtered[i].end_section! >= filtered[i].start_section!
        ? filtered[i].end_section! : filtered[i].start_section!;
      if (end > maxSection) maxSection = end;
    }
    const cards: ScheduleCard[] = [];
    for (let wd = 1; wd <= 7; wd++) {
      const dayItems = filtered.filter((it: EduScheduleItemDto) => it.weekday === wd)
        .sort((a: EduScheduleItemDto, b: EduScheduleItemDto) => {
          const sa = a.start_section !== undefined ? a.start_section : 99;
          const sb = b.start_section !== undefined ? b.start_section : 99;
          return sa - sb;
        });
      const lanes: EduScheduleItemDto[][] = [];
      const laneIndexes: number[] = [];
      for (let j = 0; j < dayItems.length; j++) {
        const item = dayItems[j];
        const start = item.start_section!;
        const end = item.end_section !== undefined && item.end_section >= start ? item.end_section : start;
        let lane = 0;
        while (lane < lanes.length && lanes[lane].some((other: EduScheduleItemDto) => {
          const otherStart = other.start_section!;
          const otherEnd = other.end_section !== undefined && other.end_section >= otherStart ? other.end_section : otherStart;
          return otherStart <= end && start <= otherEnd;
        })) lane++;
        if (lane === lanes.length) lanes.push([]);
        lanes[lane].push(item);
        laneIndexes.push(lane);
      }
      for (let j = 0; j < dayItems.length; j++) {
        const item = dayItems[j];
        const start = item.start_section!;
        const end = item.end_section !== undefined && item.end_section >= start ? item.end_section : start;
        let overlapCount = 0;
        for (let k = 0; k < dayItems.length; k++) {
          const otherItem = dayItems[k];
          if (otherItem === undefined || otherItem.start_section === undefined) continue;
          const otherStart: number = otherItem.start_section;
          const otherEnd: number = otherItem.end_section !== undefined && otherItem.end_section >= otherStart ? otherItem.end_section : otherStart;
          if (otherStart <= end && start <= otherEnd) overlapCount++;
        }
        cards.push({
          id: item.id || (wd + '_' + (item.course_code || '') + '_' + start + '_' + (item.location || '') + '_' + (item.weeks || '')),
          item: item,
          weekday: wd,
          startSection: start,
          endSection: end,
          lane: laneIndexes[j],
          laneCount: Math.max(1, Math.min(lanes.length, overlapCount)),
          course_name: item.course_name || '未命名课程',
          location: item.location || '',
          color: courseColorCode(item),
        });
      }
    }
    this.scheduleCards = cards;
    this.maxSection = maxSection;
    this.scheduleEmpty = this.allItems.length === 0;
  }

  openDetail(item: EduScheduleItemDto) {
    this.detailCourseName = item.course_name || '未命名课程';
    this.detailCourseCode = item.course_code || '';
    this.detailRows = buildDetailRows(item);
    this.detailExtraRows = buildExtraRows(item.extra_info);
    this.sheetVisible = true;
  }

  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      Column({ space: 0 }) {
        SecondaryHeader({ title: '教务课表', subtitle: '第 ' + this.currentWeek + ' 周', darkMode: this.darkMode, onBack: () => this.onBack() })

        Row({ space: 8 }) {
          Button('上一周').fontSize(13).backgroundColor(this.palette().surface).fontColor(this.palette().text)
            .enabled(this.currentWeek > 1).onClick(() => { if (this.currentWeek > 1) { this.currentWeek--; this.buildScheduleGrid(); } })
          Text('第 ' + this.currentWeek + ' 周').fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.palette().text).layoutWeight(1).textAlign(TextAlign.Center)
          Button('下一周').fontSize(13).backgroundColor(this.palette().surface).fontColor(this.palette().text)
            .enabled(this.currentWeek < 25).onClick(() => { if (this.currentWeek < 25) { this.currentWeek++; this.buildScheduleGrid(); } })
          Button('刷新').fontSize(13).backgroundColor(this.palette().surface).fontColor(this.palette().text)
            .onClick(() => this.loadSchedule())
        }.width('100%').padding(12)

        if (this.loading) {
          Column({ space: 8 }) {
            LoadingProgress().width(32).height(32).color(this.palette().primary)
          }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else if (this.scheduleEmpty) {
          Column({ space: 6 }) {
            Text('本学期暂无课程').fontSize(16).fontWeight(FontWeight.Medium).fontColor(this.palette().text)
            Text('请先在教务系统页面连接并同步课表').fontSize(12).fontColor(this.palette().muted)
          }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else if (this.scheduleCards.length === 0) {
          Text('本周没有课程').fontSize(13).fontColor(this.palette().muted).layoutWeight(1).padding(16)
        } else {
          Scroll() {
            Stack({ alignContent: Alignment.TopStart }) {
              Column({ space: 0 }) {
                Row({ space: 0 }) {
                  Text('').width(TIME_COLUMN_WIDTH).height(HEADER_HEIGHT)
                  ForEach(WEEKDAY_NAMES, (label: string) => {
                    Text(label).width(DAY_COLUMN_WIDTH).height(HEADER_HEIGHT).textAlign(TextAlign.Center)
                      .fontSize(12).fontWeight(FontWeight.Bold).fontColor(this.palette().primary)
                  }, (label: string) => label)
                }
                ForEach(Array.from({ length: this.maxSection }, (_: Object, index: number) => index + 1), (section: number) => {
                  Row({ space: 0 }) {
                    Text(section.toString()).width(TIME_COLUMN_WIDTH).height(SECTION_HEIGHT).textAlign(TextAlign.Center)
                      .fontSize(11).fontColor(this.palette().muted)
                    ForEach(WEEKDAY_NAMES, (_label: string) => {
                      Text('').width(DAY_COLUMN_WIDTH).height(SECTION_HEIGHT).border({ width: 1, color: this.palette().line })
                    }, (_label: string, index: number) => 'cell_' + section + '_' + index)
                  }
                }, (section: number) => 'section_' + section)
              }.width(TIME_COLUMN_WIDTH + DAY_COLUMN_WIDTH * 7)
              ForEach(this.scheduleCards, (card: ScheduleCard) => {
                Column({ space: 3 }) {
                  Text(card.course_name).fontSize(13).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
                    .maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis })
                  if (card.location.length > 0) {
                    Text(card.location).fontSize(11).fontColor(this.palette().muted)
                      .maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
                  }
                }.width(Math.max(44, DAY_COLUMN_WIDTH / card.laneCount - 4)).height(Math.max(44, SECTION_HEIGHT * (card.endSection - card.startSection + 1) - 4))
                  .padding(8).backgroundColor(this.palette().surface).border({ width: 2, color: card.color }).borderRadius(10)
                  .position({
                    x: TIME_COLUMN_WIDTH + DAY_COLUMN_WIDTH * (card.weekday - 1) + (DAY_COLUMN_WIDTH / card.laneCount) * card.lane + 2,
                    y: HEADER_HEIGHT + SECTION_HEIGHT * (card.startSection - 1) + 2,
                  })
                  .onClick(() => this.openDetail(card.item))
              }, (card: ScheduleCard) => card.id)
            }.width(TIME_COLUMN_WIDTH + DAY_COLUMN_WIDTH * 7).height(HEADER_HEIGHT + SECTION_HEIGHT * this.maxSection)
          }.layoutWeight(1).width('100%').scrollBar(BarState.Off).scrollable(ScrollDirection.Horizontal)
        }
      }.width('100%').height('100%').backgroundColor(this.palette().background)

      if (this.sheetVisible) {
        this.DetailOverlay()
      }
    }.width('100%').height('100%')
  }


  @Builder DetailOverlay() {
    Column({ space: 0 }) {
      Column().width('100%').layoutWeight(1).backgroundColor('#80000000').onClick(() => { this.sheetVisible = false; })
      Scroll() {
        Column({ space: 10 }) {
          Text(this.detailCourseName).fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
          if (this.detailCourseCode.length > 0) {
            Text(this.detailCourseCode).fontSize(12).fontColor(this.palette().muted)
          }
          ForEach(this.detailRows, (row: DetailRow) => {
            Row({ space: 12 }) {
              Text(row.label).fontSize(12).fontColor(this.palette().muted).width(80)
              Text(row.value).fontSize(13).fontWeight(FontWeight.Medium).fontColor(this.palette().text).layoutWeight(1)
                .maxLines(3).textOverflow({ overflow: TextOverflow.Ellipsis })
            }.width('100%')
          }, (row: DetailRow) => row.label)
          if (this.detailExtraRows.length > 0) {
            Text('更多信息').fontSize(13).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
          }
          ForEach(this.detailExtraRows, (row: DetailRow) => {
            Row({ space: 12 }) {
              Text(row.label).fontSize(12).fontColor(this.palette().muted).width(80)
              Text(row.value).fontSize(13).fontWeight(FontWeight.Medium).fontColor(this.palette().text).layoutWeight(1)
                .maxLines(3).textOverflow({ overflow: TextOverflow.Ellipsis })
            }.width('100%')
          }, (row: DetailRow) => 'extra_' + row.label)
          Text('数据来源：学校教务系统').fontSize(10).fontColor(this.palette().muted)
          Button('关闭').width('100%').height(40).backgroundColor(this.palette().surface).fontColor(this.palette().primary)
            .onClick(() => { this.sheetVisible = false; })
        }.width('100%').padding({ left: 22, right: 22, top: 16, bottom: 28 })
      }.scrollBar(BarState.Off).backgroundColor(this.palette().surface).borderRadius({ topLeft: 16, topRight: 16 }).height('70%')
    }.width('100%').height('100%')
  }
}
