<script setup>
import {
  PhArrowCounterClockwise, PhArrowRight, PhBell, PhBookOpen, PhCalendarBlank,
  PhCaretRight, PhChartBar, PhChartLineUp, PhCheckCircle, PhCheckSquare,
  PhCircle, PhClipboardText, PhClockCounterClockwise, PhFileText, PhGear,
  PhGraduationCap, PhHouse, PhList, PhLock, PhMagnifyingGlass, PhPaperPlaneTilt,
  PhPause, PhPlay, PhPlus, PhPulse, PhRobot, PhShieldCheck, PhSidebarSimple,
  PhSignOut, PhSlidersHorizontal, PhSmiley, PhSparkle, PhSquaresFour,
  PhTrash, PhUser, PhUsers, PhWarningCircle, PhEye, PhEyeSlash,
} from "@phosphor-icons/vue";
const props = defineProps({ name: { type: String, required: true }, size: { type: Number, default: 20 }, weight: { type: String, default: "regular" } });
const icons = { PhArrowCounterClockwise, PhArrowRight, PhBell, PhBookOpen, PhCalendarBlank, PhCaretRight, PhChartBar, PhChartLineUp, PhCheckCircle, PhCheckSquare, PhCircle, PhClipboardText, PhClockCounterClockwise, PhFileText, PhGear, PhGraduationCap, PhHouse, PhList, PhLock, PhMagnifyingGlass, PhPaperPlaneTilt, PhPause, PhPlay, PhPlus, PhPulse, PhRobot, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley, PhSparkle, PhSquaresFour, PhTrash, PhUser, PhUsers, PhWarningCircle, PhEye, PhEyeSlash };
const icon = icons[props.name] || PhCircle;
</script>
<template><component :is="icon" :size="size" :weight="weight" aria-hidden="true" /></template>
