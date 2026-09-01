import assert from "node:assert/strict";
import { test } from "node:test";

import { createAppRoutes } from "../src/appRoutes.js";

const stubView = Symbol("view");
const appRoutes = createAppRoutes({
  loginView: stubView,
  appShell: stubView,
  loadStudentView: () => stubView,
});

function flattenRoutes(routes, parentPath = "") {
  return routes.flatMap((route) => {
    const path = route.path.startsWith("/")
      ? route.path
      : `${parentPath.replace(/\/$/, "")}/${route.path}`;
    return [{ ...route, resolvedPath: path }, ...flattenRoutes(route.children || [], path)];
  });
}

test("authenticated web routes expose only the student experience", () => {
  const routes = flattenRoutes(appRoutes);
  const authenticatedRoutes = routes.filter((route) => !route.meta?.public && route.redirect == null);

  assert.ok(authenticatedRoutes.length > 0);
  assert.equal(routes.some((route) => route.resolvedPath.startsWith("/admin")), false);
  assert.equal(routes.some((route) => route.resolvedPath.startsWith("/teacher")), false);
  assert.deepEqual(
    [...new Set(authenticatedRoutes.flatMap((route) => route.meta?.roles || []))],
    ["student"],
  );
});
