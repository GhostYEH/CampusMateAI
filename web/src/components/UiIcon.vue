<script setup>
import {
  PhArrowClockwise, PhArrowCounterClockwise, PhArrowLeft, PhArrowRight, PhArrowUpRight,
  PhArrowsDownUp, PhArrowsLeftRight, PhArchive, PhBell, PhBellSlash, PhBookOpen, PhBuildings, PhCalendarHeart, PhChatsCircle, PhCoffee,
  PhBookmark, PhBookmarkSimple, PhCalendarBlank, PhCalendarStar, PhChalkboardTeacher,
  PhCaretDown, PhCaretLeft, PhCaretRight, PhChartBar, PhChartLineUp, PhChartLine, PhChartPie, PhCalendarPlus,
  PhChatCircleText, PhChatTeardropText, PhCheck, PhCheckCircle, PhCheckSquare,
  PhCircle, PhCircleNotch, PhDotsSixVertical,
  PhClipboardText, PhClock, PhClockCounterClockwise, PhCloudSlash, PhCopy,
  PhDownload, PhDownloadSimple, PhDotsThree, PhEnvelopeSimple, PhExam, PhFile, PhFileImage, PhFilePdf, PhFileText, PhFiles,
  PhFire, PhFlag, PhFlagCheckered, PhFolderOpen, PhFunnel, PhGear, PhGraduationCap, PhHandCoins,
  PhHourglass, PhHouse, PhIdentificationCard, PhImage, PhInfo, PhLayout, PhLightbulb, PhLinkSimpleHorizontalBreak, PhList, PhListChecks, PhLock, PhMagnifyingGlass, PhMapPin,
  PhMapTrifold, PhMedal, PhMegaphone, PhNotebook, PhNotePencil, PhPaperclip, PhPaperPlaneTilt, PhPause, PhPencil, PhPencilSimple,
  PhPaintBrush, PhPencilSimpleLine, PhPlanet, PhPlay, PhPlus, PhPulse, PhQuestion, PhQuotes, PhRobot, PhScales, PhSealCheck,
  PhQrCode, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley,
  PhSparkle, PhSquaresFour, PhStop, PhStopCircle, PhStudent, PhStorefront, PhSun, PhTag, PhTarget, PhTimer, PhTrash, PhThumbsUp, PhTrophy, PhBookOpenText,
  PhUpload, PhUser, PhUsers, PhUsersThree, PhWarning, PhWarningCircle, PhEye, PhEyeSlash, PhEraser, PhX,
} from "@phosphor-icons/vue";

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 20 },
  weight: { type: String, default: "regular" },
});

const icons = {
  PhArrowClockwise, PhArrowCounterClockwise, PhArrowLeft, PhArrowRight, PhArrowUpRight,
  PhArrowsDownUp, PhArrowsLeftRight, PhArchive, PhBell, PhBellSlash, PhBookOpen, PhBuildings, PhCalendarHeart, PhChatsCircle, PhCoffee,
  PhBookmark, PhBookmarkSimple, PhCalendarBlank, PhCalendarStar, PhChalkboardTeacher,
  PhCaretDown, PhCaretLeft, PhCaretRight, PhChartBar, PhChartLineUp, PhChartLine, PhChartPie, PhCalendarPlus,
  PhChatCircleText, PhChatTeardropText, PhCheck, PhCheckCircle, PhCheckSquare,
  PhCircle, PhCircleNotch, PhDotsSixVertical,
  PhClipboardText, PhClock, PhClockCounterClockwise, PhCloudSlash, PhCopy,
  PhDownload, PhDownloadSimple, PhDotsThree, PhEnvelopeSimple, PhExam, PhFile, PhFileImage, PhFilePdf, PhFileText, PhFiles,
  PhFire, PhFlag, PhFlagCheckered, PhFolderOpen, PhFunnel, PhGear, PhGraduationCap, PhHandCoins,
  PhHourglass, PhHouse, PhIdentificationCard, PhImage, PhInfo, PhLayout, PhLightbulb, PhLinkSimpleHorizontalBreak, PhList, PhListChecks, PhLock, PhMagnifyingGlass, PhMapPin,
  PhMapTrifold, PhMedal, PhMegaphone, PhNotebook, PhNotePencil, PhPaperclip, PhPaperPlaneTilt, PhPause, PhPencil, PhPencilSimple,
  PhPaintBrush, PhPencilSimpleLine, PhPlanet, PhPlay, PhPlus, PhPulse, PhQuestion, PhQuotes, PhRobot, PhScales, PhSealCheck,
  PhQrCode, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley,
  PhSparkle, PhSquaresFour, PhStop, PhStopCircle, PhStudent, PhStorefront, PhSun, PhTag, PhTarget, PhTimer, PhTrash, PhThumbsUp, PhTrophy, PhBookOpenText,
  PhUpload, PhUser, PhUsers, PhUsersThree, PhWarning, PhWarningCircle, PhEye, PhEyeSlash, PhEraser, PhX,
};

const icon = icons[props.name] || PhCircle;
</script>
<template><component :is="icon" :size="size" :weight="weight" aria-hidden="true" /></template>
