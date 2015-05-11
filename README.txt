USAGE

The goal of this problem is to write a program that decrypts a set of short messages (roughly the length of Tweets) that have been encrypted with a simple substitution cipher.  My solution is contained in the file `decipher.py`.  The file contains a solver class, objects of which are initialized by passing the filename of the reference corpus, e.g. 

  solver = Solver('corpus-en.txt', n_max=100, verbose=False)

where the optional argument `n_max` sets the pruning width for the breadth-first search (explained below) and the optional argument `verbose` turns on or off status printing to the terminal.  A cipher is then solved by calling the solver's `solve` method using the names of input and output filenames, e.g.

  solver.solve('encoded-en.txt', 'cipher.txt', 'decoded-en.txt')

were 'cipher.txt' will be an output file containing the mappings 'a -> h', etc.  Once the cipher has been solved, other files could be decoded using the resulting cipher key by calling

  solver.decipher('encoded-en.txt', 'decoded-en.txt')

The script as a whole can be run from the command line by specifying the relevant filenames as input arguments, e.g.

>> python decipher.py encoded_en.txt corpus_en.txt cipher.txt decoded_en.txt
-------------------------------------------------------------------------------

MOTIVATION

The task is to choose a cipher key such that the deciphered text "looks like" sensible English text.  To do this, we must first decide how to measure the "sensibleness" of the resulting text by some metric.  A number of approaches could be taken for this.  One would be to try to make the frequencies of character n-grams match those in the reference corpus.  (A quick Google search reveals stochastic "hill-climbing" solutions to the problem along these lines.)  A different approach, more similar to how a human might solve the problem, is to find matches for the ciphered text at the word level, by looking at the pattern of characters in each word and finding likely matches in the reference text.  For example, commonly occurring single-character words are likely to be "I" or "a", while common three-letter words with distinct characters might be "the" or "and".  I decided to try this latter approach.  

REFERENCE CORPUS REPRESENTATION

The first step in solving the problem is to extract relevant statistics from the reference corpus.  In our case, we need to know which words are in the text and to get their relative frequencies/probabilities.  The Solver class's constructor reads in the corpus text and computes word counts, using the CountVectorizer class from sci-kit learn for convenience.  For the purposes here, a word is defined as a sequence of non-numeric characters separated by any combination of punctuation or whitespace.  

To aid in solving the cipher, we take the log of each word count, which assigns a score to each word proportional to its log-probability in the reference text.  (A value of 1 is first added to the word count to pad the probabilities of missing words.)  These word-score pairs are stored in a dictionary for fast access.  

Additionally, to aid in matching the character pattern of the reference words to the enciphered text, each word is converted to a standard character "pattern" in which its characters have been replaced alphabetically in their order of appearance.  For example, the word "dotted" is represented by the pattern "abccda".  A dictionary mapping each pattern to a list of word-score tuples (ordered by score) is also stored by the constructor.  

SOLUTION METHOD

To solve the cipher, the Solution class's `solve` method reads the enciphered text and converts it to a list of words, word counts, and character patterns, similarly to the constructor method.  The general approach is to take these words one by one in decreasing order of their frequency, and find potential matches to their character patterns from the reference corpus.  For example, the most common word in `encoded-en.txt` is "qml", which could translate to "the", "and", "his", "was", and so forth.  Each of these choices restricts the choice of matches for the following words.  For instance, the choice of "qml" -> "the" restricts the possible matches for the second most common word, "zl", to words ending in "e", for instance "be", "me", "we", etc.  Because each choice of a match for a word generates a potentially different set of possible matches next word, the partial solutions at each stage of the algorithm form a tree structure.  The task is to find the path through the tree (i.e. the assignment of encoded words to reference words) that **maximizes the joint probability of the decoded text**.  We will accomplish this using a breadth-first search.  

Formally, we represent a single (potentially incomplete) solution as a named tuple consisting of the fields:
- `score`: the joint log-probability (sum of scores) of the words so far assigned
- `words`: the list of deciphered words matched to the cipher's words so far, in decreasing order of the cipher words' frequency
- `fw_key`: a (incomplete) dictionary mapping deciphered to enciphered characters 
- `bw_key`: a (incomplete) dictionary mapping enciphered to deciphered characters 
Note that the `words` field is strictly unnecessary but helps with debugging.  

Now, given a (incomplete) solution and an enciphered word to be matched, we define the method `__spawn()` which returns the extended solutions corresponding to the `max_n` most probable matches to the word that are consistent with the existing solution, as determined the reference data.  That is, the method:
- uses the enciphered word's character pattern to look up the list of possible matching reference words
- loops through the possible matches (in decreasing order of probability) and checks if each is consistent with the solution determined so far
- generates a new extended solution for each of the consistent matches and returns them as a list.  
The `__spawn` function implicitly defines a tree of possible solutions, with the tree's root the empty solution and with the tree's leaves having matched (or attempted to match) all the words in the ciphered text.  (Note that if no solutions are found, a single extended solution is returned with `None` as the match word and with a score of 0 assigned.  Also, if the word is already deciphered by the partial solution, a single extended solution is returned with updated values for the `score` and `words` fields.)  

To perform the breadth-first search, we first seed the algorithm with an empty solution (the root of the tree), and then loop through the list of words from the enciphered text.  For each word, we use the solutions existing from the previous step to spawn new, extended solutions corresponding to possible matches for the current word.  To prevent geometric expansion of the number of solutions, we then prune the tree back to the `max_n` solutions with highest log probability before moving on to the next iteration.  In the end, we select the tree leaf with the highest probability as the overall solution.  

DISCUSSION AND FURTHER DIRECTIONS

The algorithm is not guaranteed to reach the best solution.  In particular, if the correct match for an enciphered word ranks very low in probability, it may not land in the top `max_n` solutions and may be pruned off.  This outcome is unlikely, however, because we consider the words in descending order of their frequency in the ciphered text.  It is improbable, for example, that the word "uml", which is the most frequently occuring word in the test text, translates to a very rare word.  (In fact, it translates to "the".)  Furthermore, after the first few words are assigned to matches, the number of possible matches for the remaining words are severely restricted, and are likely to be fewer than `max_n` anyway.  For the code here, I used `max_n`=100 to be safe, but using `max_n`>=19 gives the correct solution for the provided cipher.  (The sticking point is the word "wisdom", which while common in the cipher text is relatively uncommon in the reference corpus.)  For test ciphers with highly unusual word statistics, the max_n value could be adjusted upward at the cost of longer runtimes.  

The described pruning approach allows the code to run in seconds for the selected value of `max_n`.  The code could be further optimized by improving the search for potential match words consistent with an existing solution.  (Currently the program searches through potential matches one by one and checks each character for consistency.)   Additionally, while for the given cipher the word-level probabilities were enough to determine the correct solution, for shorter utterances there is a small chance that the most probable word-level translation would be nonsensical overall at the sentence level.  In this case word bi-grams or higher-order n-grams could be substituted for the word statistics used here.  
