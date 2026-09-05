import {
  ArrowClockwise, ArrowLeft, ArrowRight, ArrowUpRight, ArrowsClockwise,
  Bell, BookOpen, BookOpenText, Bookmark, BookmarkSimple, Buildings, Copy,
  Calendar, CalendarBlank, CaretRight, Check, CheckCircle, CheckSquare,
  ChatCircle, ChatsCircle, Circle, ClipboardText, Clock, Envelope, EnvelopeOpen,
  Exam, Eye, EyeSlash, File, Files, FileText, Flag, FolderOpen, Gear, GraduationCap, Heart,
  HeartStraight, House, Info, Link as LinkIcon, List, ListChecks, Lock,
  MagnifyingGlass, Megaphone, PaperPlaneRight, Pause, Pencil, Play, Plus,
  PlusCircle, QrCode, Robot, SignOut, Sparkle, Stack, Target, Timer, Trash,
  User, UserCircle, WarningCircle, X, IdentificationCard, MapPin, ShieldCheck,
  Notebook, EnvelopeSimple, ChartLineUp, SealCheck, ClockCounterClockwise,
  Student, PaintBrush, Layout, Planet, SquaresFour,
  Question, Users, HandCoins, Coffee, Storefront, CalendarHeart, Lightbulb,
  DotsThree, NotePencil, ChatCircleText, UsersThree,
  Fire, FlagCheckered, MapTrifold, ChalkboardTeacher, TreasureChest, Star,
  SpeakerSimpleLow, SpeakerSimpleHigh, SpeakerSimpleX, Waveform,
} from "@phosphor-icons/react";

const icons = { ArrowClockwise, ArrowLeft, ArrowRight, ArrowUpRight, ArrowsClockwise, Bell, BookOpen, BookOpenText, Bookmark, BookmarkSimple, Buildings, Copy, Calendar, CalendarBlank, CaretRight, Check, CheckCircle, CheckSquare, ChatCircle, ChatsCircle, Circle, ClipboardText, Clock, Envelope, EnvelopeOpen, Exam, Eye, EyeSlash, File, Files, FileText, Flag, FolderOpen, Gear, GraduationCap, Heart, HeartStraight, House, IdentificationCard, Info, Link: LinkIcon, List, ListChecks, Lock, MagnifyingGlass, MapPin, Megaphone, PaperPlaneRight, Pause, Pencil, Play, Plus, PlusCircle, QrCode, Robot, ShieldCheck, SignOut, Sparkle, SquaresFour, Stack, Target, Timer, Trash, User, UserCircle, WarningCircle, X, Notebook, EnvelopeSimple, ChartLineUp, SealCheck, ClockCounterClockwise, Student, PaintBrush, Layout, Planet, Question, Users, HandCoins, Coffee, Storefront, CalendarHeart, Lightbulb, DotsThree, NotePencil, ChatCircleText, UsersThree, Fire, FlagCheckered, MapTrifold, ChalkboardTeacher, TreasureChest, Star, SpeakerSimpleLow, SpeakerSimpleHigh, SpeakerSimpleX, Waveform };

export function Icon({ name = "PhSparkle", size = 20, weight = "regular", ...props }) {
  const canonicalName = name.startsWith("Ph") ? name.slice(2) : name;
  const Component = icons[name] || icons[canonicalName] || Sparkle;
  return <Component size={size} weight={weight} aria-hidden="true" {...props} />;
}
