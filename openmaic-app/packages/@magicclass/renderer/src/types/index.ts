// The slide object model is the canonical contract from @magicclass/dsl. The renderer
// no longer vendors its own copy; it re-exports the DSL types here so the public
// `@magicclass/renderer/types` surface stays intact.
export * from '@magicclass/dsl';
export * from './effects';
