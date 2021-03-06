import tensorflow as tf
import data
import config
import os
import sys

import numpy as np

from attention_model import AttentionChatBotModel
from basic_model import BasicChatBotModel


def _check_restore_parameters(sess, saver, ckpt_path):
    """ Restore the previously trained parameters if there are any. """
    ckpt = tf.train.get_checkpoint_state(os.path.dirname(ckpt_path))
    if ckpt and ckpt.model_checkpoint_path:
        print("Loading parameters for the Chatbot")
        saver.restore(sess, ckpt.model_checkpoint_path)
    else:
        print("Initializing fresh parameters for the Chatbot")


def _get_user_input():
    """ Get user's input, which will be transformed into encoder input later """
    print("> ", end="")
    sys.stdout.flush()
    return sys.stdin.readline().encode('ascii')


def _construct_response(output_logits, inv_dec_vocab):
    """ Construct a response to the user's encoder input.
    @output_logits: the outputs from sequence to sequence wrapper.
    output_logits is decoder_size np array, each of dim 1 x DEC_VOCAB

    This is a greedy decoder - outputs are just argmaxes of output_logits.
    """
    print("logits: ", output_logits[0])
    outputs = [int(np.argmax(logit, axis=1)) for logit in output_logits[0]]
    print(outputs)
    # If there is an EOS symbol in outputs, cut them at that point.
    if config.EOS_ID in outputs:
        outputs = outputs[:outputs.index(config.EOS_ID)]
    # Print out sentence corresponding to outputs.
    return " ".join([tf.compat.as_str(inv_dec_vocab[output]) for output in outputs])


def chat(use_attention, ckpt_path="./ckp-dir/checkpoints"):
    """ in test mode, we don't to create the backward path
    """
    _, enc_vocab = data.load_vocab(
        os.path.join(config.PROCESSED_PATH, 'vocab.enc'))
    inv_dec_vocab, _ = data.load_vocab(
        os.path.join(config.PROCESSED_PATH, 'vocab.dec'))

    if not use_attention:
        model = BasicChatBotModel(batch_size=1)
    else:
        model = AttentionChatBotModel(batch_size=1)
    model.build()

    saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        _check_restore_parameters(sess, saver, ckpt_path)
        output_file = open(os.path.join(
            config.PROCESSED_PATH, config.OUTPUT_FILE), 'a+')
        # Decode from standard input.
        max_length = config.BUCKETS[-1][0]
        print(
            'Welcome to TensorBro. Say something. Enter to exit. Max length is', max_length)
        while True:
            line = _get_user_input()
            if len(line) > 0 and line[-1] == b'\n':
                line = line[:-1]
            if line == b'':
                break
            output_file.write('HUMAN ++++ ' + line.decode('ascii') + '\n')
            # Get token-ids for the input sentence.
            token_ids = data.sentence2id(enc_vocab, line)
            if len(token_ids) > max_length:
                print('Max length I can handle is:', max_length)
                line = _get_user_input()
                continue
            # Which bucket does it belong to?
            # bucket_id = _find_right_bucket(len(token_ids))
            bucket_id = -1
            # Get a 1-element batch to feed the sentence to the model.
            encoder_inputs, decoder_inputs, decoder_masks = data.get_batch([(token_ids, [])],
                                                                           bucket_id,
                                                                           batch_size=1)
            # Get output logits for the sentence.
            decoder_lens = np.sum(np.transpose(np.array(decoder_masks), (1, 0)), axis=1)
            output_logits = sess.run([model.final_outputs],
                                     feed_dict={model.encoder_inputs_tensor: encoder_inputs,
                                                model.decoder_inputs_tensor: decoder_inputs,
                                                model.decoder_length_tensor: decoder_lens,
                                                model.bucket_length: config.BUCKETS[bucket_id]})
            response = _construct_response(output_logits, inv_dec_vocab)
            print(response)
            output_file.write('BOT ++++ ' + response + '\n')
        output_file.write('=============================================\n')
        output_file.close()


if __name__ == '__main__':
    chat(False, ckpt_path="./ckp-dir/basic-step_100-batch_64-lr_0.001-3_layers_with_weights/checkpoints")
