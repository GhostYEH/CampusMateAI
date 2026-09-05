import test from "node:test";
import assert from "node:assert/strict";
import * as api from "../src/data/api.js";

const requiredFunctions = [
  "login", "probeBackend", "qrCreate", "qrStatus", "qrExchange",
  "getDashboard", "getCourses", "getCourseDetail", "getAssignments",
  "getTasks", "createTask", "updateTask", "completeTask", "deleteTask",
  "analyzeTaskImport", "commitTaskImport", "getAssignment", "getSubmission",
  "saveSubmission", "submitSubmission", "getStudySessions", "getActiveStudySession",
  "startStudySession", "pauseStudySession", "resumeStudySession", "finishStudySession",
  "breakdownStudyTask", "getExams", "saveExam", "deleteExam", "getUniversities",
  "selectUniversity", "getCommunityPosts", "getCommunityCategories", "getCommunityPost",
  "createCommunityPost", "updateCommunityPost", "deleteCommunityPost", "likePost",
  "unlikePost", "favoritePost", "unfavoritePost", "getComments", "createComment",
  "reportPost", "uploadCommunityImage", "getAnnouncement", "markAnnouncementRead",
  "getProfile", "updateProfile", "getAcademicStatus", "getAcademicProviders",
  "getEduBinding", "bindEdu", "unbindEdu", "syncEdu", "getEduSyncRecords",
  "probeEduPortal", "createEduConnection", "getEduConnection", "continueEduConnection",
  "pollEduConnection", "preLoginEdu", "getScheduleItems", "getGradeItems", "getExamItems",
  "getChaoxingStatus", "loginChaoxing", "syncChaoxing", "disconnectChaoxing",
  "chatStream", "streamAssistantSpeech", "extractNotice",
];

test("React data adapter exposes every required backend capability", () => {
  for (const name of requiredFunctions) assert.equal(typeof api[name], "function", name);
});
