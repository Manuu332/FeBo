import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import random
from pathlib import Path

class Vocab:
    def __init__(self):
        self.word2idx = {"<pad>":0, "<unk>":1, "<eos>":2}
        self.idx2word = {0:"<pad>",1:"<unk>",2:"<eos>"}
        self.next_idx = 3
    def add_word(self, word):
        if word not in self.word2idx:
            self.word2idx[word] = self.next_idx
            self.idx2word[self.next_idx] = word
            self.next_idx += 1
        return self.word2idx[word]
    def encode(self, sentence, max_len=20):
        tokens = sentence.lower().split()
        return [self.word2idx.get(w,1) for w in tokens[:max_len]]
    def decode(self, idxs):
        return " ".join([self.idx2word.get(i,"<unk>") for i in idxs if i not in (0,2)])
    def size(self):
        return self.next_idx

class TinyBrain(nn.Module):
    def __init__(self, vocab_size, hidden_size=48, embed_size=24):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_size, padding_idx=0)
        self.gru = nn.GRU(embed_size, hidden_size, batch_first=True)
        self.out = nn.Linear(hidden_size, vocab_size)
    def forward(self, x, hidden=None):
        x = self.embed(x)
        out, hidden = self.gru(x, hidden)
        logits = self.out(out)
        return logits, hidden

class EmergentReasoner:
    def __init__(self, hidden_size=48, lr=0.001):
        self.vocab = Vocab()
        self.device = torch.device("cpu")
        self.network = TinyBrain(self.vocab.size(), hidden_size).to(self.device)
        self.optimizer = optim.Adam(self.network.parameters(), lr=lr)
        self.saved_log_probs = []
        self.temperature = 1.2
        self._load()
    def _save(self):
        torch.save({
            'network': self.network.state_dict(),
            'vocab': {
                'word2idx': self.vocab.word2idx,
                'idx2word': self.vocab.idx2word,
                'next_idx': self.vocab.next_idx
            }
        }, Path("memory/feebo_brain.pt"))
    def _load(self):
        p = Path("memory/feebo_brain.pt")
        if p.exists():
            try:
                data = torch.load(p, map_location=self.device)
                # Restore vocab FIRST so we know the correct network size
                self.vocab.word2idx = data['vocab']['word2idx']
                self.vocab.idx2word = {int(k): v for k, v in data['vocab']['idx2word'].items()}
                self.vocab.next_idx = data['vocab']['next_idx']
                # Build network at saved vocab size, THEN load weights
                self.network = TinyBrain(self.vocab.size()).to(self.device)
                self.network.load_state_dict(data['network'])
            except Exception as e:
                # Checkpoint incompatible — start fresh (vocab still restored above)
                import logging
                logging.getLogger("febo.emergent_nn").warning(
                    f"Could not load brain weights ({e}). Starting fresh."
                )
                self.network = TinyBrain(max(self.vocab.size(), 3)).to(self.device)
    def generate_response(self, user_input, max_tokens=15):
        input_idxs = self.vocab.encode(user_input)
        if not input_idxs:
            input_idxs = [self.vocab.add_word("hello")]
        input_tensor = torch.tensor([input_idxs], device=self.device)
        _, hidden = self.network(input_tensor)
        generated = []
        current_token = torch.tensor([[self.vocab.word2idx.get("<eos>")]], device=self.device)
        for _ in range(max_tokens):
            logits, hidden = self.network(current_token, hidden)
            probs = F.softmax(logits[:, -1, :] / self.temperature, dim=-1)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            self.saved_log_probs.append(dist.log_prob(action))
            token = action.item()
            generated.append(token)
            if token == self.vocab.word2idx.get("<eos>"):
                break
            current_token = torch.tensor([[token]], device=self.device)
        response = self.vocab.decode(generated)
        self.last_input = user_input
        self.last_response = response
        return response
    def reward_feedback(self, reward):
        if not self.saved_log_probs:
            return
        R = torch.tensor([reward], device=self.device)
        policy_loss = []
        for log_prob in self.saved_log_probs:
            policy_loss.append(-log_prob * R)
        self.optimizer.zero_grad()
        policy_loss = torch.cat(policy_loss).sum()
        policy_loss.backward()
        self.optimizer.step()
        self.saved_log_probs = []
        for w in (self.last_input + " " + self.last_response).split():
            self.vocab.add_word(w)
        if self.vocab.size() > self.network.out.out_features:
            self._rebuild_network()
        self._save()
    def _rebuild_network(self):
        new_net = TinyBrain(self.vocab.size()).to(self.device)
        old_dict = self.network.state_dict()
        new_dict = new_net.state_dict()
        for k in old_dict:
            if k in new_dict and old_dict[k].shape == new_dict[k].shape:
                new_dict[k] = old_dict[k]
        new_net.load_state_dict(new_dict)
        self.network = new_net

reasoner = EmergentReasoner()
