<script setup>
import {
  PhArrowClockwise, PhArrowCounterClockwise, PhArrowLeft, PhArrowRight,
  PhArrowsDownUp, PhArrowsLeftRight, PhArchive, PhBell, PhBellSlash, PhBookOpen, PhBuildings, PhCalendarHeart, PhChatsCircle, PhCoffee,
  PhBookmark, PhBookmarkSimple, PhCalendarBlank, PhCalendarStar, PhChalkboardTeacher,
  PhCaretDown, PhCaretLeft, PhCaretRight, PhChartBar, PhChartLineUp, PhChartLine, PhChartPie,
  PhChatCircleText, PhChatTeardropText, PhCheck, PhCheckCircle, PhCheckSquare,
  PhCircle, PhCircleNotch,
  PhClipboardText, PhClock, PhClockCounterClockwise, PhCloudSlash, PhCopy,
  PhDownload, PhDownloadSimple, PhDotsThree, PhEnvelopeSimple, PhExam, PhFile, PhFileImage, PhFilePdf, PhFileText, PhFiles,
  PhFlag, PhFlagCheckered, PhFolderOpen, PhFunnel, PhGear, PhGraduationCap, PhHandCoins,
  PhHourglass, PhHouse, PhIdentificationCard, PhImage, PhInfo, PhLightbulb, PhLinkSimpleHorizontalBreak, PhList, PhListChecks, PhLock, PhMagnifyingGlass, PhMapPin,
  PhMegaphone, PhNotebook, PhNotePencil, PhPaperclip, PhPaperPlaneTilt, PhPause, PhPencil,
  PhPencilSimpleLine, PhPlay, PhPlus, PhPulse, PhQuestion, PhQuotes, PhRobot, PhScales, PhSealCheck,
  PhQrCode, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley,
  PhSparkle, PhSquaresFour, PhStop, PhStopCircle, PhStudent, PhStorefront, PhTag, PhTrash, PhThumbsUp,
  PhUpload, PhUser, PhUsers, PhUsersThree, PhWarningCircle, PhEye, PhEyeSlash, PhEraser, PhX,
} from "@phosphor-icons/vue";

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 20 },
  weight: { type: String, default: "regular" },
});

const icons = {
  PhArrowClockwise, PhArrowCounterClockwise, PhArrowLeft, PhArrowRight,
  PhArrowsDownUp, PhArrowsLeftRight, PhArchive, PhBell, PhBellSlash, PhBookOpen, PhBuildings, PhCalendarHeart, PhChatsCircle, PhCoffee,
  PhBookmark, PhBookmarkSimple, PhCalendarBlank, PhCalendarStar, PhChalkboardTeacher,
  PhCaretDown, PhCaretLeft, PhCaretRight, PhChartBar, PhChartLineUp, PhChartLine, PhChartPie,
  PhChatCircleText, PhChatTeardropText, PhCheck, PhCheckCircle, PhCheckSquare,
  PhCircle, PhCircleNotch,
  PhClipboardText, PhClock, PhClockCounterClockwise, PhCloudSlash, PhCopy,
  PhDownload, PhDownloadSimple, PhDotsThree, PhEnvelopeSimple, PhExam, PhFile, PhFileImage, PhFilePdf, PhFileText, PhFiles,
  PhFlag, PhFlagCheckered, PhFolderOpen, PhFunnel, PhGear, PhGraduationCap, PhHandCoins,
  PhHourglass, PhHouse, PhIdentificationCard, PhImage, PhInfo, PhLightbulb, PhLinkSimpleHorizontalBreak, PhList, PhListChecks, PhLock, PhMagnifyingGlass, PhMapPin,
  PhMegaphone, PhNotebook, PhNotePencil, PhPaperclip, PhPaperPlaneTilt, PhPause, PhPencil,
  PhPencilSimpleLine, PhPlay, PhPlus, PhPulse, PhQuestion, PhQuotes, PhRobot, PhScales, PhSealCheck,
  PhQrCode, PhShieldCheck, PhSidebarSimple, PhSignOut, PhSlidersHorizontal, PhSmiley,
  PhSparkle, PhSquaresFour, PhStop, PhStopCircle, PhStudent, PhStorefront, PhTag, PhTrash, PhThumbsUp,
  PhUpload, PhUser, PhUsers, PhUsersThree, PhWarningCircle, PhEye, PhEyeSlash, PhEraser, PhX,
};

const icon = icons[props.name] || PhCircle;
</script>
<template><component :is="icon" :size="size" :weight="weight" aria-hidden="true" /></template>
