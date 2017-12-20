# -*- coding: utf-8 -*-

from __future__ import print_function
import random
import re

import colorama
import numpy as np

colorama.init()


def print_green(*args, **kwargs):
    print(colorama.Fore.GREEN, end='')
    print(*args, **kwargs)
    print(colorama.Style.RESET_ALL, end='')


def print_cyan(*args, **kwargs):
    print(colorama.Fore.CYAN, end='')
    print(*args, **kwargs)
    print(colorama.Style.RESET_ALL, end='')


def print_red(*args, **kwargs):
    print(colorama.Fore.RED, end='')
    print(*args, **kwargs)
    print(colorama.Style.RESET_ALL, end='')


# Samples an unnormalized array of probabilities. Use temperature to
# flatten/amplify the probabilities.
def sample_preds(preds, temperature=1.0):
    preds = np.asarray(preds).astype(np.float64)
    # Add a tiny positive number to avoid invalid log(0)
    preds += np.finfo(np.float64).tiny
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)


# Basic word tokenizer based on the Penn Treebank tokenization script, but
# setup to handle multiple sentences. Newline aware, i.e. newlines are replaced
# with a specific token. You may want to consider using a more robust tokenizer
# as a preprocessing step, and using the --pristine-input flag.
def word_tokenize(text):
    regexes = [
        # Starting quotes
        (re.compile(r'(\s)"'), r'\1 “ '),
        (re.compile(r'([ (\[{<])"'), r'\1 “ '),
        # Punctuation
        (re.compile(r'([:,])([^\d])'), r' \1 \2'),
        (re.compile(r'([:,])$'), r' \1 '),
        (re.compile(r'\.\.\.'), r' ... '),
        (re.compile(r'([;@#$%&])'), r' \1 '),
        (re.compile(r'([?!\.])'), r' \1 '),
        (re.compile(r"([^'])' "), r"\1 ' "),
        # Parens and brackets
        (re.compile(r'([\]\[\(\)\{\}\<\>])'), r' \1 '),
        # Double dashes
        (re.compile(r'--'), r' -- '),
        # Ending quotes
        (re.compile(r'"'), r' ” '),
        (re.compile(r"([^' ])('s|'m|'d) "), r"\1 \2 "),
        (re.compile(r"([^' ])('ll|'re|'ve|n't) "), r"\1 \2 "),
        # Contractions
        (re.compile(r"\b(can)(not)\b"), r' \1 \2 '),
        (re.compile(r"\b(d)('ye)\b"), r' \1 \2 '),
        (re.compile(r"\b(gim)(me)\b"), r' \1 \2 '),
        (re.compile(r"\b(gon)(na)\b"), r' \1 \2 '),
        (re.compile(r"\b(got)(ta)\b"), r' \1 \2 '),
        (re.compile(r"\b(lem)(me)\b"), r' \1 \2 '),
        (re.compile(r"\b(mor)('n)\b"), r' \1 \2 '),
        (re.compile(r"\b(wan)(na)\b"), r' \1 \2 '),
        # Newlines
        (re.compile(r'\n'), r' \\n ')
    ]

    text = " " + text + " "
    for regexp, substitution in regexes:
        text = regexp.sub(substitution, text)
    return text.split()


# A hueristic attempt to undo the Penn Treebank tokenization above. Pass the
# --pristine-output flag if no attempt at detokenizing is desired.
def word_detokenize(tokens):
    regexes = [
        # Newlines
        (re.compile(r'[ ]?\\n[ ]?'), r'\n'),
        # Contractions
        (re.compile(r"\b(can)\s(not)\b"), r'\1\2'),
        (re.compile(r"\b(d)\s('ye)\b"), r'\1\2'),
        (re.compile(r"\b(gim)\s(me)\b"), r'\1\2'),
        (re.compile(r"\b(gon)\s(na)\b"), r'\1\2'),
        (re.compile(r"\b(got)\s(ta)\b"), r'\1\2'),
        (re.compile(r"\b(lem)\s(me)\b"), r'\1\2'),
        (re.compile(r"\b(mor)\s('n)\b"), r'\1\2'),
        (re.compile(r"\b(wan)\s(na)\b"), r'\1\2'),
        # Ending quotes
        (re.compile(r"([^' ]) ('ll|'re|'ve|n't)\b"), r"\1\2"),
        (re.compile(r"([^' ]) ('s|'m|'d)\b"), r"\1\2"),
        (re.compile(r'[ ]?”'), r'"'),
        # Double dashes
        (re.compile(r'[ ]?--[ ]?'), r'--'),
        # Parens and brackets
        (re.compile(r'([\[\(\{\<]) '), r'\1'),
        (re.compile(r' ([\]\)\}\>])'), r'\1'),
        (re.compile(r'([\]\)\}\>]) ([:;,.])'), r'\1\2'),
        # Punctuation
        (re.compile(r"([^']) ' "), r"\1' "),
        (re.compile(r' ([?!\.])'), r'\1'),
        (re.compile(r'([^\.])\s(\.)([\]\)}>"\']*)\s*$'), r'\1\2\3'),
        (re.compile(r'([#$]) '), r'\1'),
        (re.compile(r' ([;%:,])'), r'\1'),
        # Starting quotes
        (re.compile(r'(“)[ ]?'), r'"')
    ]

    text = ' '.join(tokens)
    for regexp, substitution in regexes:
        text = regexp.sub(substitution, text)
    return text.strip()


# Heuristic attempt to find some good seed strings in the input text
def find_random_seeds(text, num_seeds=50, max_seed_length=50):
    lines = text.split('\n')
    # Take a random sampling of lines
    if len(lines) > num_seeds * 4:
        lines = random.sample(lines, num_seeds * 4)
    # Take the top quartile based on length so we get decent seed strings
    lines = sorted(lines, key=len, reverse=True)
    lines = lines[:num_seeds]
    # Split on the first whitespace before max_seed_length
    return [line[:max_seed_length].rsplit(None, 1)[0] for line in lines]


# Reformat our data vector to feed into our model. Tricky with stateful rnn
def reshape_for_stateful_rnn(sequence, batch_size, seq_length, seq_step):
    passes = []
    # Take strips of our data at seq_step intervals up to our seq_length
    # and cut those strips into seq_length sequences
    for offset in range(0, seq_length, seq_step):
        pass_samples = sequence[offset:]
        num_pass_samples = pass_samples.size // seq_length
        pass_samples = np.resize(pass_samples,
                                 (num_pass_samples, seq_length))
        passes.append(pass_samples)
    # Stack our samples together and make sure they fit evenly into batches
    all_samples = np.concatenate(passes)
    num_batches = all_samples.shape[0] // batch_size
    num_samples = num_batches * batch_size
    # Now the tricky part, we need to reformat our data so the first
    # sequence in the nth batch picks up exactly where the first sequence
    # in the (n - 1)th batch left off, as the lstm cell state will not be
    # reset between batches in the stateful model.
    reshuffled = np.zeros((num_samples, seq_length), dtype=np.int32)
    for batch_index in range(batch_size):
        # Take a slice of num_batches consecutive samples
        slice_start = batch_index * num_batches
        slice_end = slice_start + num_batches
        index_slice = all_samples[slice_start:slice_end, :]
        # Spread it across each of our batches in the same index position
        reshuffled[batch_index::batch_size, :] = index_slice
    return reshuffled
