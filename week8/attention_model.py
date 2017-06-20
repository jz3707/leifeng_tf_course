import tensorflow as tf
from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import tensor_array_ops

import config
from basic_model import BasicChatBotModel


class AttentionChatBotModel(BasicChatBotModel):
    def decode(self, enc_outputs, enc_final_state):
        with tf.variable_scope('decoder') as scope:
            scope = tf.get_variable_scope()
            scope.set_initializer(tf.random_uniform_initializer(-0.1, 0.1))

            W = tf.get_variable(
                name="W",
                shape=[config.DEC_VOCAB, config.HIDDEN_SIZE],
                initializer=tf.random_uniform_initializer(-0.1, 0.1))
            target_embedded = tf.nn.embedding_lookup(W, self.decoder_inputs_tensor)

            cell = tf.nn.rnn_cell.GRUCell(num_units=config.HIDDEN_SIZE)

            def condition(time, all_outputs, inputs, states):
                return time < config.BUCKETS[0][1] - 1
                # return tf.reduce_all(self.decoder_length_tensor > time)

            def body(time, all_outputs, inputs, states):
                dec_outputs, dec_state = cell(inputs=inputs, state=states)

                # calculate attention
                att_keys = tf.contrib.layers.fully_connected(inputs=enc_outputs, num_outputs=config.CONTEXT_SIZE,
                                                             activation_fn=None)
                att_query = tf.contrib.layers.fully_connected(inputs=dec_outputs, num_outputs=config.CONTEXT_SIZE,
                                                              activation_fn=None)
                scores = tf.reduce_sum(att_keys * tf.expand_dims(att_query, 0), [2])
                scores_normalized = tf.nn.softmax(scores, dim=0)
                context = tf.expand_dims(scores_normalized, 2) * enc_outputs
                context = tf.reduce_sum(context, [0], name="context")
                print(dec_outputs.get_shape())
                print(att_keys.get_shape())
                print(att_query.get_shape())
                print(scores.get_shape())
                print(scores_normalized.get_shape())
                print(context.get_shape())

                projection_input = tf.concat([dec_outputs, context], 1)
                print("projection_input:", projection_input.get_shape())
                output_logits = tf.contrib.layers.fully_connected(inputs=projection_input, num_outputs=config.DEC_VOCAB,
                                                                  activation_fn=None)
                print("output_logits:", output_logits.get_shape())
                all_outputs = all_outputs.write(time, output_logits)

                output_label = tf.arg_max(output_logits, dimension=1)
                next_input_embedding = tf.nn.embedding_lookup(W, output_label)
                next_input_embedding.set_shape((self.batch_size, config.HIDDEN_SIZE))
                next_input = tf.concat([next_input_embedding, context], 1)
                # next_input = tf.concat([target_embedded[time + 1], context], 1)

                return time + 1, all_outputs, next_input, dec_state

            output_ta = tensor_array_ops.TensorArray(dtype=tf.float32,
                                                     size=0,
                                                     dynamic_size=True,
                                                     element_shape=(self.batch_size, config.DEC_VOCAB))

            init_inputs = tf.concat(
                [target_embedded[0], tf.zeros(dtype=tf.float32, shape=(self.batch_size, config.CONTEXT_SIZE))],
                1)
            print("init_inputs:", init_inputs.get_shape())

            res = control_flow_ops.while_loop(
                condition,
                body,
                loop_vars=[0, output_ta, init_inputs, enc_final_state],
            )
            final_outputs = res[1].stack()
            final_state = res[3]
        return final_outputs, final_state
