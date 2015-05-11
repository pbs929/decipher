'''
decipher.py - Script for solving a substitution cipher

Author: Phillip Schafer (phillip.baker.schafer@mg.thedataincubator.com)
Date: May 4, 2015

Usage:
>> python decipher.py encoded_en.txt corpus_en.txt cipher.txt decoded_en.txt
'''

import sys
import string
import codecs
import math
from sklearn.feature_extraction.text import CountVectorizer
from collections import namedtuple

ALPHABET = string.ascii_lowercase
SOLUTION = namedtuple('SOLUTION', ['score', 'words', 'fw_key', 'bw_key'])

class Solver(object):
    '''
    Class for solving a simple substitution cipher.

    constructor:
    Solver(ref_filename, max_n=100, verbose=False)

    public methods:
    solve(self, cipher_file, keyout_file=None, textout_file=None)
    decipher(self, cipher_file, textout_file=None)
    '''

    def __init__(self, ref_file, max_n=100, verbose=False):
        '''
        Read the reference file and store wordcounts as class variables:
        - a dictionary mapping words to their log probabilities
        - a dictionary mapping character patterns (e.g. 'abccda' for 'dotted')
          to a list of words and their log probabilities, sorted by probability
        '''
        self.max_n = max_n
        self.verbose = verbose
        if self.verbose:
            print 'processing reference file...'

        # Get words and word probabilities from text and put in dictionary
        self.vectorizer = CountVectorizer(token_pattern=r'(?u)\b[a-zA-Z]+\b')
        wordcounts = self.__get_wordcounts(ref_file)
        self.word_dict = {word:math.log(count+1.0) for count, word in wordcounts}

        # Also put words and probabilities into the dictionary keyed by pattern
        self.words_by_pattern = {}
        for count, word in wordcounts:
            pattern = self.__word_to_pattern(word)
            prob = math.log(count+1.0)
            if pattern in self.words_by_pattern:
                self.words_by_pattern[pattern].append((prob, word))
            else:
                self.words_by_pattern[pattern] = [(prob, word)]

        # Initial null solution
        self.solution = None
        if self.verbose:
            print '...done\n'

    def __get_wordcounts(self, filename):
        ''' Get a list of (word, count) tuples from a file, sort by count'''
        text = codecs.open(filename, 'r', 'utf-8-sig').read()
        count_mtx = self.vectorizer.fit_transform([text])
        counts = count_mtx.toarray()[0]
        words = self.vectorizer.get_feature_names()
        return sorted(zip(counts, words), reverse=True)

    def __word_to_pattern(self, word):
        '''
        Convert a word to its character pattern, e.g. 'dotted' -> 'abccda'
        '''
        key = {}
        pattern = []
        ind = 0
        for letter in word.lower():
            if letter not in key:
                key[letter] = ALPHABET[ind]
                ind += 1
            pattern.append(key[letter])
        return ''.join(pattern)


    def solve(self, cipher_file, keyout_file=None, textout_file=None):
        '''
        Solve the ciphered text contained in the cipher file and print the
        resulting key and deciphered text to output files, if provided.

        A solution consists of:
        - a score (log probability)
        - a list of match words for each word in the ciphered text
        - a forward and backwards cipher dictionary

        To reach a solution, we consider the ciphered words in decreasing order
        of their frequency.  For each ciphered word, we:
        - take each existing candidate solution, and spawn possible extensions
          of that solution that match the word with a word from the reference
          text (while remaining compatible with the existing solution)
        - eliminate low-probability options to prevent geometric ballooning
          of the solution set
        '''
        self.default_min = 0 # default log prob if no match found
        cipher_words = self.__get_wordcounts(cipher_file)

        # create seed solution and perform main loop
        solutions = [SOLUTION(score=0, words=[], fw_key={}, bw_key={})]
        counter = 1
        for word_count, word in cipher_words:
            if self.verbose:
                print 'matching word', counter, 'of', len(cipher_words)
                counter += 1
            pattern = self.__word_to_pattern(word)
            new_solns = []
            for soln in solutions:
                new_solns.extend(self.__spawn(soln, word, pattern, word_count))
            # select only the `max_n` best solutions
            new_solns.sort(reverse=True)
            solutions = new_solns[:self.max_n]

        # Store the best solution, with missing values arbitrarily assigned
        self.solution = self.__fill_in(solutions[0])

        # Write the decryption key to file
        if keyout_file:
            f = codecs.open(keyout_file, 'w', 'utf-8-sig')
            for a in ALPHABET:
                f.write(a + ' -> ' + self.solution.bw_key[a] + '\n')

        # Solve the cipher and write to file, if provided
        self.decipher(cipher_file, textout_file)

    def __spawn(self, soln, test_word, test_pattern, test_word_count):
        '''
        Given an incomplete solution and a new word to match (plus its pattern
        and word count), return a list of extended solutions corresponding to
        the possible matches of the new word.

        If this test word is already decoded by the solution, we generate a
        single extended solution with the score and word list updated.
        Otherwise, if the pattern exists in the reference text, we find the top
        `max_n` possible matches (at most) and append to the list of extended
        solutions.

        If there's no match for the pattern, we return a list consisting of a
        single extended solution with 'none' added to the list of match words.
        '''
        new_solns = []
        if all([c in soln.bw_key for c in test_word]):  # word already solved
            ref_word = self.__decode_text(test_word, soln)
            if ref_word in self.word_dict:
                ref_count = self.word_dict[ref_word]
                score = ref_count*test_word_count
                new_solns.append(self.__extend_solution(
                        soln, score, ref_word, fw_key={}, bw_key={}))
        elif test_pattern in self.words_by_pattern:
            for ref_count, ref_word in self.words_by_pattern[test_pattern]:
                fw_key, bw_key = self.__match_key(test_word, ref_word, soln)
                if fw_key is not None:
                    score = ref_count*test_word_count
                    new_solns.append(self.__extend_solution(
                        soln, score, ref_word, fw_key, bw_key))
                if len(new_solns) >= self.max_n:
                    break
        # default if no matches found
        if len(new_solns) == 0:
            new_solns.append(self.__extend_solution(
                    soln, score=0, word=None, fw_key={}, bw_key={}))
        return new_solns

    def __match_key(self, test_word, ref_word, soln):
        '''
        Determine whether a (ciphered) test word could match a reference word,
        given a partial solution.  If so, return the extended forward and
        backward keys resulting from the match.

        The match fails if the test letter already deciphers to the wrong
        letter in the reference word.  It also fails if the letter is not in
        the solution, but adding it would lead to multiple letters mapping to
        the same output.
        '''
        fw_key = {}
        bw_key = {}
        for i in xrange(len(test_word)):
            if test_word[i] in soln.bw_key:
                if soln.bw_key[test_word[i]] != ref_word[i]:
                    return None, None
            elif ref_word[i] in soln.fw_key:
                return None, None
            else:
                bw_key[test_word[i]] = ref_word[i]
                fw_key[ref_word[i]] = test_word[i]
        return fw_key, bw_key

    def __extend_solution(self, soln, score, word, fw_key, bw_key):
        ''' Add a test word-reference word match to an existing solution '''
        fw_new = soln.fw_key.copy()
        bw_new = soln.bw_key.copy()
        fw_new.update(fw_key)
        bw_new.update(bw_key)
        return SOLUTION(score=soln.score+score, words=soln.words+[word],
                        fw_key=fw_new, bw_key=bw_new)

    def __fill_in(self, soln):
        '''
        Fill in an arbitrary mapping for any letters not already assigned in a
        solution
        '''
        fw_free = []
        bw_free = []
        for a in ALPHABET:
            if a not in soln.fw_key:
                fw_free.append(a)
            if a not in soln.bw_key:
                bw_free.append(a)
        new_soln = SOLUTION(score=soln.score, words=soln.words,
                            fw_key=soln.fw_key, bw_key=soln.bw_key)
        for fw,bw in zip(fw_free, bw_free):
            new_soln.fw_key[fw] = bw
            new_soln.bw_key[bw] = fw
        return new_soln


    def decipher(self, cipher_file, textout_file=None):
        '''
        Decipher a file containing ciphered text and write the result to a
        file, if provided.  If no solution has yet been found, call the `solve`
        method on the ciphered text file.
        '''
        if self.solution is None:
            self.solve(cipher_file)
        in_text = codecs.open(cipher_file, 'r', 'utf-8-sig').read()
        out_text = self.__decode_text(in_text, self.solution)
        if textout_file:
            codecs.open(textout_file, 'w', 'utf-8-sig').write(out_text)
        if self.verbose:
            print '\nDECIPHERED TEXT: \n'
            print out_text.encode('ascii', 'ignore')

    def __decode_text(self, text, solution):
        ''' Decipher text using a given Solution. '''
        out = []
        for letter in text:
            if letter.lower() in solution.bw_key:
                if letter.isupper():
                    out.append(solution.bw_key[letter.lower()].upper())
                else:
                    out.append(solution.bw_key[letter.lower()])
            else:
                out.append(letter)
        return ''.join(out)

def main():
    ''' Run the code on files provided as command line arguments '''
    try:
        cipher_file = sys.argv[1]
        ref_file = sys.argv[2]
        keyout_file = sys.argv[3]
        textout_file = sys.argv[4]
    except IndexError:
        print "Usage: decipher.py <cipher_file> <reference_file> <keyout_file> <textout_file>"
        sys.exit(1)

    solver = Solver(ref_file, max_n=100, verbose=True)
    solver.solve(cipher_file, keyout_file, textout_file)

if __name__ == "__main__":
    main()
