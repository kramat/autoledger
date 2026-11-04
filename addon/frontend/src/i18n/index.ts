// Interface language: English and Dutch.
//
// Texts live per area in en/*.ts; nl/*.ts has the same keys, and the TypeScript
// build fails when a Dutch text is missing. `t('fuel.title')` looks a text up,
// `{name}` placeholders are filled from the second argument, and keys ending in
// `.one` / `.other` are counted forms for `tn()`.
// Calls read `lang`, so templates and computed values follow a language change.

import { ref } from 'vue'
import en from './en'
import nl from './nl'

export type Lang = 'en' | 'nl'
export type LanguagePreference = 'auto' | Lang

type Leaves<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>
}[keyof T & string]

export type Messages = typeof en
export type Key = Leaves<Messages>
type PluralKey = Key extends infer K ? (K extends `${infer B}.one` ? B : never) : never
type Params = Record<string, string | number>

const DICTIONARIES: Record<Lang, Messages> = { en, nl }

/** The browser's first preferred language, when we have it; English otherwise. */
export function browserLanguage(): Lang {
  const preferred = navigator.languages?.length ? navigator.languages : [navigator.language]
  for (const tag of preferred) {
    const base = tag?.toLowerCase().split('-')[0]
    if (base === 'nl' || base === 'en') return base
  }
  return 'en'
}

export const lang = ref<Lang>(browserLanguage())

export function setLanguagePreference(preference: LanguagePreference | undefined): void {
  lang.value = !preference || preference === 'auto' ? browserLanguage() : preference
  document.documentElement.lang = lang.value
}

/** Locale for numbers and dates: Dutch in Dutch, otherwise the browser's own. */
export function locale(): string | undefined {
  return lang.value === 'nl' ? 'nl-NL' : undefined
}

function lookup(dictionary: Messages, key: string): string | undefined {
  let node: unknown = dictionary
  for (const part of key.split('.')) {
    if (node == null || typeof node !== 'object') return undefined
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === 'string' ? node : undefined
}

function fill(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match))
}

export function t(key: Key, params?: Params): string {
  const text = lookup(DICTIONARIES[lang.value], key) ?? lookup(en, key)
  if (text === undefined) {
    console.warn(`Missing text: ${key}`)
    return key
  }
  return fill(text, params)
}

/** A counted text: `{n}` is the count, `.one` is used for exactly 1. */
export function tn(key: PluralKey, n: number, params?: Params): string {
  return t(`${key}.${n === 1 ? 'one' : 'other'}` as Key, { n, ...params })
}
