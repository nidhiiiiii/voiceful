# notes

## hackathon postmortem

shipped parrot in a weekend. the voice profile actually held up. the bit i underestimated was how much the few-shot examples carry the output. you can have all the stats in the world but if your few-shot examples are mid, the model will write mid.

biggest lesson: don't put 500 samples in one prompt. batch them. merge results. obvious in hindsight.

## TIL

TIL git log has --since with relative dates. "git log --since=2.weeks" is the cleanest thing i've seen in a while. been writing python date math for years to do this.

TIL telegram inline keyboards eat callbacks if your handler raises. they don't surface the error anywhere. you just get a spinning button forever. cursed.

TIL pyperclip on linux needs xclip installed at the OS level. failed silently for me for an hour.

## stuff that didn't work

tried using the same drafter for twitter and linkedin with just length variation. the linkedin output was tweet-shaped which read as deeply weird on linkedin. you have to actually change the structure not just the cap.

tried generating 5 drafts at once and asking the user to pick. nobody picks. they edit the first one and ignore the rest.

## opinions

most "AI assistant" tools are not actually agents. they're autocomplete in a sidebar. an agent watches and acts. a sidebar waits and answers.

the moat for these tools is not the model. it's the context. who has the best signal of what you're doing right now.
