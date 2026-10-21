# The taste model: shorts

Learnt 2026-10-21 from 8 shorts by 4 creators (seed 0): 135 pairs, each a real edit against a copy the computer damaged in one way. Only numbers and labels went in; none of anyone's video, frames or words.

## Can it tell a real edit from a damaged one?

- On a creator it never saw (leave one creator out): **66%** of pairs.
- On a damage it was never shown (that damage and that creator both left out): **28%** on average.
- 50% is a coin toss; a tie counts half.

| Damage | What the computer did | Creator never seen | Damage never shown |
| --- | --- | --- | --- |
| shuffle_all | every shot in a random order | 75% | 62% |
| swap_neighbours | a few shots swapped with the next one | 50% | 38% |
| even_rhythm | every shot the same length | 62% | 0% |
| permute_durations | the shots in order, their lengths handed out at random | 25% | 25% |
| add_flashes | white flashes on many joins | 100% | 100% |
| add_dissolves | dissolves on many joins | 100% | 100% |
| quantise_to_beat | every cut moved onto the beat (or a half-second grid) | 12% | 12% |
| cold_open | the held first shot cut to a typical length | 25% | 25% |
| long_open | the first shot held three times as long | 62% | 0% |
| fade_in_out | a fade from black at the start and to black at the end | 100% | 19% |
| no_fades | the creator's fades from or to black taken off | 0% | 0% |
| words_top | the words moved to the top of the frame | 100% | 88% |
| words_caps | the words in capitals | 100% | 0% |
| words_lower | the creator's capitals in lower case | 0% | 0% |
| words_everywhere | words over every shot | 0% | 0% |
| words_none | the words taken out | 50% | 0% |
| long_talk | the cutaways between talking shots taken out | 0% | 0% |
| repeat_shot | a shot shown again later on | 100% | 75% |
| stretch_ending | the last shot held three times as long | 75% | 12% |
| cold_ending | the held last shot cut to a typical length | 50% | 50% |
| music_off | the music taken away | 75% | 0% |
| add_music | music under all of it | 0% | 0% |

A damage the second column can't see is one only that damage teaches; a high first column with a low second one means the model learnt that damage, not editing.

## What it weighs

The strongest signals; a + means the real edits have more of it than the damaged ones.

- -1.43  music under less or more of it than in the good edits
- -1.32  share of shots that are a shot shown earlier
- -0.99  words on fewer or more shots than in the good edits
- -0.99  how long the last shot is held, against the typical shot
- -0.92  fades out to black at the end
- -0.84  more or fewer capitals than in the good edits
- -0.84  shot lengths more even or more uneven than the good edits'
- -0.84  words at the top more or less often than in the good edits
- +0.84  opens on a hook
- -0.82  how long laughing shots are held, against the typical shot
- -0.76  share of held shots that land after a quick run
- -0.73  how long a caption stays up

## Story jobs (the role model)

Not trained: on a creator it never saw it names 44% of jobs right, against 42% for always guessing the commonest.

## Grammar

Shot lengths and joins learnt from 8 videos; what each shot is, by the readings there were: faces, motion, sound (8), faces, motion (8), motion, sound (8), motion (8); story jobs from 8.

## Read with care

- The real side is what these creators did, not proof of what is good; the damaged side is the computer's idea of a mistake. The model learns what separates the two.
- The sample is the creators, not the videos: 4 here. Each creator counts the same however many videos they gave.
- A reading that wasn't taken (no faces off the Mac, no words when Vision didn't run) counts as neither good nor bad.
- Every threshold that turns readings into tokens (quick, held, talking, moving) is a prior.
