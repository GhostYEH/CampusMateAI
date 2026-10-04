import { useCallback, useEffect, useRef, useState } from "react";

/** Keep the latest request when dependencies change or a caller reloads. */
export function useAsyncResource(load, dependencies) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const loadRef = useRef(load);
  const mounted = useRef(false);
  const requestVersion = useRef(0);
  // These values identify the resource, rather than the recreated loader. Use
  // React's Object.is comparison so equivalent key lists do not refetch.
  const identityRef = useRef(dependencies);
  if (dependencies.length !== identityRef.current.length ||
      dependencies.some((value, index) => !Object.is(value, identityRef.current[index]))) {
    identityRef.current = dependencies;
  }
  const identity = identityRef.current;
  loadRef.current = load;

  const reload = useCallback(() => {
    if (!mounted.current) return Promise.resolve();
    const version = ++requestVersion.current;
    const request = loadRef.current;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    return Promise.resolve()
      .then(request)
      .then(
        (data) => {
          if (mounted.current && version === requestVersion.current) {
            setState({ loading: false, data, error: null });
          }
        },
        (error) => {
          if (mounted.current && version === requestVersion.current) {
            setState({ loading: false, data: null, error });
          }
        },
      );
  }, []);

  useEffect(() => {
    mounted.current = true;
    reload();
    return () => {
      mounted.current = false;
      requestVersion.current += 1;
    };
  }, [identity, reload]);

  return { ...state, reload };
}
