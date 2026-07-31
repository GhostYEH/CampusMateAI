<script setup>
import {
  PhArrowCounterClockwise, PhArrowRight, PhBell, PhBookOpen, PhBookmarkSimple, PhCalendarBlank,
  PhCalendarStar, PhChalkboardTeacher,
  PhCaretRight, PhChartBar, PhChartLineUp, PhCheckCircle, PhCheckSquare,
  PhCheck, PhCircle, PhClipboardText, PhClock, PhClockCounterClockwise, PhFileText, PhGear,
  PhGraduationCap, PhHouse, PhList, PhLock, PhMagnifyingGlass, PhPaperPlaneTilt,
  PhPause, PhPlay, PhPlus, PhPulse, PhRobot, PhShieldCheck, PhSidebarSimple,
  PhSignOut, PhSlidersHorizontal, PhSmiley, PhSparkle, PhSquaresFour, PhStopCircle,
  PhStudent, PhTrash, PhUser, PhUsers, PhWarningCircle, PhEye, PhEyeSlash,
  PhX,
} from "@phosphor-icons/vue";
const props = defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 20 }, weight: { type: String, default: "regular" } });
const icons = { PhArrowCounterClockwise, PhArrowRight, PhBell, PhBookOpen, PhBookmarkSimple, PhCalendarBlank, PhCalendarStar, PhChalkboardTeacher, PhCaretRight, PhChartBar, PhChartLineUp, PhCheck, PhCheckCircle, PhCheckSquare, PhCircle, PhClipboardText, PhClock, PhClockCounterClockwise, PhFileText, PhGear, PhGraduationCap, PhHouse, PhList, PhLock, PhMagnifyingGlass, PhPaperPlaneTilt, PhPause, PhPlay, PhPlus, PhPulse, PhRobot, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley, PhSparkle, PhSquaresFour, PhStopCircle, PhStudent, PhTrash, PhUser, PhUsers, PhWarningCircle, PhEye, PhEyeSlash, PhX };
const icon = icons[props.name] || PhCircle;
</script>
<template><component :is="icon" :size="size" :weight="weight" aria-hidden="true" /></template>
