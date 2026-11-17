# Parametric memory

**In plain words:** the general knowledge the model picked up in training, stored in its weights, which are the learned numbers inside the model. It is why the model can understand language, write code or explain a common idea without looking anything up. (video)

**What to build:** nothing. This skill is for agents that call a hosted model, one that another company runs and your code reaches over the internet. You cannot change the model. The design file has no row for it. Answer A8 in section 1 names the model and what it cannot know.

It still shapes the design, in three ways.

## What it means for the rest of the design

- **It can be out of date.** The model knows the world as of its training. Anything that changes (prices, policies, who holds a role, today's date) must come from a source the app controls. (video)
- **It cannot know private information.** Orders, accounts, internal documents, what this user said last month: the model has none of it unless the app puts it in the context window. (video)
- **A normal call does not change it.** Nothing the user says today is in the model tomorrow. If it must survive, it goes in semantic or episodic memory. (video)

So the rule: current, exact or private facts come from semantic memory or retrieval, never from the model's own knowledge. (video)

## Questions

- M1. Which model does the agent use?
- M2. From step 1, question A8: what does the agent need to know that the model cannot know? Each item on that list must have a row in section 3 (it is saved) or section 6 (it is looked up). If the list is empty, as for an agent that only rewrites the text it is given, nothing more is needed.

## Code to build

No store. Two small things in other places, when they matter to the agent:

- In the instructions: tell the model to use only what it was given for facts about the user, the company and anything that changes. An agent that answers people says when it was not given the answer; one that acts does not act on a guess.
- In the function that builds the model call: put today's date in, if dates matter to the agent.

## Tests that try to break it

Only for an agent that looks things up or saves facts:

- Remove a private or current fact it needs (an order status with the lookup turned off). An agent that answers says it does not have it; one that acts does not act. Neither guesses.
- Change a policy in the store. Run the agent on it. What it does follows the store, not what the model might have seen in training.

## Out of scope

Fine-tuning is further training that changes the weights. It can change style or behaviour, but it is a poor place for facts that change often. (video) This skill does not cover it.
