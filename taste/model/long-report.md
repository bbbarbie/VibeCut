# The taste model: long vlogs

Learnt 2026-10-21 from 24 long vlogs by 8 creators (seed 0): 409 pairs, each a real edit against a copy the computer damaged in one way. Only numbers and labels went in; none of anyone's video, frames or words.

## Can it tell a real edit from a damaged one?

- On a creator it never saw (leave one creator out): **90%** of pairs.
- On a damage it was never shown (that damage and that creator both left out): **27%** on average.
- 50% is a coin toss; a tie counts half.

| Damage | What the computer did | Creator never seen | Damage never shown |
| --- | --- | --- | --- |
| shuffle_all | every shot in a random order | 100% | 96% |
| swap_neighbours | a few shots swapped with the next one | 71% | 71% |
| even_rhythm | every shot the same length | 96% | 0% |
| permute_durations | the shots in order, their lengths handed out at random | 79% | 62% |
| add_flashes | white flashes on many joins | 100% | 100% |
| add_dissolves | dissolves on many joins | 100% | 17% |
| strip_effects | the creator's effects between shots turned into straight cuts | 0% | 0% |
| quantise_to_beat | every cut moved onto the beat (or a half-second grid) | 96% | 75% |
| cold_open | the held first shot cut to a typical length | 9% | 9% |
| long_open | the first shot held three times as long | 92% | 8% |
| fade_in_out | a fade from black at the start and to black at the end | 100% | 0% |
| no_fades | the creator's fades from or to black taken off | 0% | 0% |
| words_top | the words moved to the top of the frame | 100% | 0% |
| words_off_top | the creator's top-of-frame words moved to the bottom | 91% | 18% |
| words_caps | the words in capitals | 100% | 17% |
| words_lower | the creator's capitals in lower case | 80% | 20% |
| words_everywhere | words over every shot | 96% | 50% |
| words_none | the words taken out | 100% | 25% |
| long_talk | the cutaways between talking shots taken out | 50% | 17% |
| repeat_shot | a shot shown again later on | 100% | 0% |
| music_off | the music taken away | 91% | 0% |
| add_music | music under all of it | 91% | 9% |

A damage the second column can't see is one only that damage teaches; a high first column with a low second one means the model learnt that damage, not editing.

## What it weighs

The strongest signals; a + means the real edits have more of it than the damaged ones.

- -2.10  music under less or more of it than in the good edits
- -1.98  words at the top more or less often than in the good edits
- -1.74  how much neighbouring shots differ in length, against chance (1: as if in any order)
- -1.72  shot lengths more even or more uneven than the good edits'
- -1.54  the longest talk with no cutaway, as a share of the video
- -1.48  more or fewer capitals than in the good edits
- +1.39  share of the words' time at the top of the frame
- -1.23  share of shots that are a shot shown earlier
- -1.06  words on fewer or more shots than in the good edits
- +1.01  how much the order of talk, faces and b-roll follows the good edits, beyond what's in it
- -0.98  share of the time with music under it
- -0.98  share of shot lengths in whole beats, as a metronome cuts

## Story jobs (the role model)

Trained on 2001 shots whose job the AI editor named; names a creator's shots right 51% of the time when it never saw that creator, against 30% for always guessing the commonest job. Jobs seen: detail 322, hook 220, other 9, payoff 129, reaction 39, setup 190, step 602, talk 421, title 18, transit 51.

## Grammar

Shot lengths and joins learnt from 24 videos; what each shot is, by the readings there were: faces, motion, sound (24), faces, motion (24), motion, sound (24), motion (24); story jobs from 24.

## Read with care

- The real side is what these creators did, not proof of what is good; the damaged side is the computer's idea of a mistake. The model learns what separates the two.
- The sample is the creators, not the videos: 8 here. Each creator counts the same however many videos they gave.
- A reading that wasn't taken (no faces off the Mac, no words when Vision didn't run) counts as neither good nor bad.
- Every threshold that turns readings into tokens (quick, held, talking, moving) is a prior.
