<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import ClassicStudentHome from "../../components/home/ClassicStudentHome.vue";
import GamifiedStudentHome from "../../components/home/gamified/GamifiedStudentHome.vue";
import { useStudentDashboardData } from "../../composables/useStudentDashboardData";
import { useAppStore } from "../../stores/app";

const props = defineProps({ searchQuery: { type: String, default: "" } });
const router = useRouter();
const store = useAppStore();
const query = computed(() => props.searchQuery);
const { state, load } = useStudentDashboardData({ searchQuery: query });

function navigate(path) {
  void router.push(path);
}

function openDue(item) {
  navigate(item.route || (item.kind === "作业" ? `/tasks/assignment/${item.id}` : `/tasks/personal/${item.id}`));
}

</script>

<template>
  <GamifiedStudentHome
    v-if="store.dashboardStyle === 'gamified'"
    :state="state"
    @navigate="navigate"
    @reload="load"
  />
  <ClassicStudentHome
    v-else
    :state="state"
    :search-query="searchQuery"
    @navigate="navigate"
    @open-due="openDue"
    @reload="load"
  />
</template>
