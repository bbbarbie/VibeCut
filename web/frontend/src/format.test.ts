import assert from 'node:assert/strict'
import { test } from 'node:test'
import { cents, centsRange } from './format.ts'

test('a cost reads the way people say it', () => {
  assert.equal(cents(0), '0¢')
  assert.equal(cents(0.004), '<1¢')
  assert.equal(cents(0.012), '1¢')
  assert.equal(cents(0.27), '27¢')
  assert.equal(cents(1.2), '$1.20')
  assert.equal(cents(0.996), '$1.00')   // never "100¢"
  assert.equal(cents(0.994), '99¢')
})

test('an estimate is one range', () => {
  assert.equal(centsRange([0.012, 0.031]), '1–3¢')
  assert.equal(centsRange([0.004, 0.02]), '<1¢–2¢')
  assert.equal(centsRange([0.011, 0.012]), '1¢')
  assert.equal(centsRange([0.5, 1.5]), '50¢–$1.50')
})
