import { useCallback, useEffect, useRef, useState } from "react";

/** Keep the latest request when dependencies change or a caller reloads. */
export function useAsyncResource(load, dependencies) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const loadRef = useRef(load);
  const mounted = useRef(false);
  const requestVersion = useRef(0);
  const identityRef = useRef(null);

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
    return () => {
      mounted.current = false;
      requestVersion.current += 1;
      identityRef.current = null;
    };
  }, []);

  // Only committed renders may replace the active identity and loader.
  useEffect(() => {
    loadRef.current = load;
    const previous = identityRef.current;
    if (!previous || dependencies.length !== previous.length ||
        dependencies.some((value, index) => !Object.is(value, previous[index]))) {
      identityRef.current = [...dependencies];
      void reload();
    }
  });

  return { ...state, reload };
}
