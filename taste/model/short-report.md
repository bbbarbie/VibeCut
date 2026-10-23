# The taste model: shorts

Learnt 2026-10-23 from 28 shorts by 12 creators (seed 0): 503 pairs, each a real edit against a copy the computer damaged in one way. Only numbers and labels went in; none of anyone's video, frames or words.

## Can it tell a real edit from a damaged one?

- On a creator it never saw (leave one creator out): **85%** of pairs.
- On a damage it was never shown (that damage and that creator both left out): **24%** on average.
- 50% is a coin toss; a tie counts half.

| Damage | What the computer did | Creator never seen | Damage never shown |
| --- | --- | --- | --- |
| shuffle_all | every shot in a random order | 100% | 93% |
| swap_neighbours | a few shots swapped with the next one | 68% | 68% |
| even_rhythm | every shot the same length | 93% | 0% |
| permute_durations | the shots in order, their lengths handed out at random | 68% | 57% |
| add_flashes | white flashes on many joins | 96% | 93% |
| add_dissolves | dissolves on many joins | 100% | 4% |
| strip_effects | the creator's effects between shots turned into straight cuts | 0% | 0% |
| quantise_to_beat | every cut moved onto the beat (or a half-second grid) | 89% | 4% |
| cold_open | the held first shot cut to a typical length | 14% | 0% |
| long_open | the first shot held three times as long | 82% | 4% |
| fade_in_out | a fade from black at the start and to black at the end | 96% | 0% |
| no_fades | the creator's fades from or to black taken off | 0% | 0% |
| words_top | the words moved to the top of the frame | 100% | 36% |
| words_off_top | the creator's top-of-frame words moved to the bottom | 67% | 0% |
| words_caps | the words in capitals | 100% | 0% |
| words_lower | the creator's capitals in lower case | 83% | 0% |
| words_everywhere | words over every shot | 80% | 13% |
| words_none | the words taken out | 89% | 0% |
| long_talk | the cutaways between talking shots taken out | 90% | 80% |
| repeat_shot | a shot shown again later on | 100% | 32% |
| stretch_ending | the last shot held three times as long | 82% | 11% |
| cold_ending | the held last shot cut to a typical length | 25% | 25% |
| music_off | the music taken away | 88% | 46% |
| add_music | music under all of it | 100% | 0% |

A damage the second column can't see is one only that damage teaches; a high first column with a low second one means the model learnt that damage, not editing.

## What it weighs

The strongest signals; a + means the real edits have more of it than the damaged ones.

- -2.14  music under less or more of it than in the good edits
- -1.84  words on fewer or more shots than in the good edits
- -1.82  words at the top more or less often than in the good edits
- +1.80  share of the time with music under it
- -1.58  share of the time with words on screen
- +1.54  how much the order of quick and held shots follows the good edits, beyond the lengths
- -1.51  share of shots that are a shot shown earlier
- -1.41  more or fewer capitals than in the good edits
- +1.36  how much longer talking shots run than the rest
- -1.33  shot lengths more even or more uneven than the good edits'
- +1.25  opens on a hook
- -1.16  the longest shot inside standing out less or more than in the good edits

## Story jobs (the role model)

Not trained: on a creator it never saw it names 55% of jobs right, against 50% for always guessing the commonest.

## Grammar

Shot lengths and joins learnt from 28 videos; what each shot is, by the readings there were: faces, motion, sound (28), faces, motion (28), motion, sound (28), motion (28); story jobs from 28.

## Read with care

- The real side is what these creators did, not proof of what is good; the damaged side is the computer's idea of a mistake. The model learns what separates the two.
- The sample is the creators, not the videos: 12 here. Each creator counts the same however many videos they gave.
- A reading that wasn't taken (no faces off the Mac, no words when Vision didn't run) counts as neither good nor bad.
- Every threshold that turns readings into tokens (quick, held, talking, moving) is a prior.
