// ponytail: history API 기반 path 라우터. react-router 의존성 없이 URL ↔ 뷰 동기화.
// 라우트: / (home) · /project/:pid (board) · /project/:pid/new · /project/:pid/t/:tid (drawer) · /decisions · /deploy
import { useEffect, useState } from "react";

export type Route =
  | { view: "home" }
  | { view: "board"; pid: number }
  | { view: "new"; pid: number }
  | { view: "decisions" }
  | { view: "deploy" }
  | { view: "ticket"; pid: number; tid: number };

export function parsePath(path: string): Route {
  const seg = path.split("/").filter(Boolean);
  if (seg.length === 0) return { view: "home" };
  if (seg[0] === "decisions") return { view: "decisions" };
  if (seg[0] === "deploy") return { view: "deploy" };
  if (seg[0] === "project" && seg[1]) {
    const pid = Number(seg[1]);
    if (!Number.isFinite(pid)) return { view: "home" };
    if (seg[2] === "new") return { view: "new", pid };
    if (seg[2] === "t" && seg[3]) {
      const tid = Number(seg[3]);
      if (Number.isFinite(tid)) return { view: "ticket", pid, tid };
    }
    return { view: "board", pid };
  }
  return { view: "home" };
}

export function useRoute(): [Route, (to: string) => void] {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = (to: string) => {
    if (to === window.location.pathname) return;
    window.history.pushState({}, "", to);
    setPath(to);
  };

  return [parsePath(path), navigate];
}
