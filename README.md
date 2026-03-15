<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

<a href="https://trendshift.io/repositories/16144" target="_blank"><img src="https://trendshift.io/api/badge/repositories/16144" alt="666ghj%2FMiroFish | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

Simple and versatile swarm intelligence engine,Predict everything
</br>
<em>A Simple and Universal Swarm Intelligence Engine, Predicting Anything</em>

<a href="https://www.shanda.com/" target="_blank"><img src="./static/image/shanda_logo.png" alt="666ghj%2MiroFish | Shanda" height="40"/></a>

[![GitHub Stars](https://img.shields.io/github/stars/666ghj/MiroFish?style=flat-square&color=DAA520)](https://github.com/666ghj/MiroFish/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/666ghj/MiroFish?style=flat-square)](https://github.com/666ghj/MiroFish/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/666ghj/MiroFish?style=flat-square)](https://github.com/666ghj/MiroFish/network)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/666ghj/MiroFish)

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1469200078932545606/1469201282077163739)
[![X](https://img.shields.io/badge/X-Follow-000000?style=flat-square&logo=x&logoColor=white)](https://x.com/mirofish_ai)
[![Instagram](https://img.shields.io/badge/Instagram-Follow-E4405F?style=flat-square&logo=instagram&logoColor=white)](https://www.instagram.com/mirofish_ai/)

[English](./README-EN.md) | [Chinese documentation](./README.md)

</div>

## ⚡ Project overview

**MiroFish** It is a new generation AI prediction engine based on multi-agent technology..By extracting real-world seed information(such as breaking news,draft policy,financial signals),Automatically build a high-fidelity parallel digital world.within this space,Thousands of people with independent personalities,Intelligent agents with long-term memory and behavioral logic interact freely and social evolution.you can pass"God's perspective"Dynamically inject variables,Accurately deduce future trends——**Let the future be previewed in the digital sandbox,Help decision-makers win after hundreds of battle simulations**.

> You just need:Upload torrent material(Data analysis report or interesting novel story),and use natural language to describe predicted needs</br>
> MiroFish will return:A detailed forecast report,and a deeply interactive, high-fidelity digital world

### our vision

MiroFish Committed to creating group intelligent mirrors that map reality,By capturing the emergence of groups triggered by individual interactions,Breaking through the limitations of traditional forecasting:

- **Yu Macro**:We are a rehearsal laboratory for policymakers,Let policy and public relations trial and error with zero risk
- **Yu Weiwei**:We are a creative sandbox for individual users,Whether it’s deducing the ending of a novel or exploring your imagination,All can be interesting,fun,Within reach

From serious prediction to fun simulation,We allow every if to see the result,Make it possible to predict everything.

## 🌐 Online experience

Welcome to the online Demo demonstration environment,Experience a prediction of hot public opinion events that we have prepared for you:[mirofish-live-demo](https://666ghj.github.io/mirofish-demo/)

## 📸 System screenshot

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/Running screenshot 1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/Running screenshot 2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/Running screenshot 3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/Running screenshot 4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/Running screenshot 5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/Running screenshot 6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

## 🎬 Demo video

### 1. Wuhan University public opinion deduction prediction + MiroFish project explanation

<div align="center">
<a href="https://www.bilibili.com/video/BV1VYBsBHEMY/" target="_blank"><img src="./static/image/Wuhan University simulation demonstration cover.png" alt="MiroFish Demo Video" width="75%"/></a>

Click on the picture to view the image generated using Weiyu BettaFish《Wuhan University Public Opinion Report》Full demo video of making predictions
</div>

### 2. 《Dream of Red Mansions》Lost ending prediction

<div align="center">
<a href="https://www.bilibili.com/video/BV1cPk3BBExq" target="_blank"><img src="./static/image/Dream of Red Mansions simulation deduction cover.jpg" alt="MiroFish Demo Video" width="75%"/></a>

Click on the image to see based on《Dream of Red Mansions》The first 80 chapters contain hundreds of thousands of words,MiroFishIn-depth prediction of lost endings
</div>

> **Financial direction deduction and forecasting**,**Deduction and prediction of current political news**The examples will be updated one after another...

## 🔄 Workflow

1. **Map construction**:Realistic seed extraction & Individual and group memory injection & GraphRAGbuild
2. **Environment setup**:Entity relationship extraction & Character generation & Environment configuration Agent injection simulation parameters
3. **Start simulation**:Dual platform parallel simulation & Automatically analyze and forecast demand & Dynamically update timing memory
4. **Report generation**:ReportAgentRich toolset for in-depth interaction with the post-simulation environment
5. **Deep interaction**:Have a conversation with anyone in the simulation world & Conversation with ReportAgent

## 🚀 quick start

### one,Source code deployment(recommend)

#### Prerequisites

| tool | Version requirements | illustrate | Installation check |
|------|---------|------|---------|
| **Node.js** | 18+ | Front-end operating environment,include npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | Backend operating environment | `python --version` |
| **uv** | Latest version | Python Package manager | `uv --version` |

#### 1. Configure environment variables

```bash
# Copy the sample configuration file
cp .env.example .env

# Edit .env file,Fill in the necessary API keys
```

**Required environment variables:**

```env
# LLM APIConfiguration(Supports any LLM API in OpenAI SDK format)
# It is recommended to use the qwen-plus model of Alibaba Bailian platform:https://bailian.console.aliyun.com/
# Note that consumption is high,You can try simulations with less than 40 rounds first
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud Configuration
# Free monthly quota can support simple use:https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key
```

#### 2. Install dependencies

```bash
# Install all dependencies in one click(Root directory + front end + back end)
npm run setup:all
```

Or install it step by step:

```bash
# Install Node dependencies(Root directory + front end)
npm run setup

# Install Python dependencies(rear end,Automatically create virtual environments)
npm run setup:backend
```

#### 3. Start service

```bash
# Start the front and back ends at the same time(Execute in the project root directory)
npm run dev
```

**Service address:**
- front end:`http://localhost:3000`
- Backend API:`http://localhost:5001`

**Start alone:**

```bash
npm run backend   # Start backend only
npm run frontend  # Start frontend only
```

### two,Docker deploy

```bash
# 1. Configure environment variables(Same source code deployment)
cp .env.example .env

# 2. Pull the image and start it
docker compose up -d
```

By default, the file in the root directory will be read. `.env`,and map the port `3000(front end)/5001(rear end)`

> exist `docker-compose.yml` The acceleration mirror address has been provided through comments in,Can be replaced as needed

## 📬 More communication

<div align="center">
<img src="./static/image/QQgroup.png" alt="QQCommunication group" width="60%"/>
</div>

&nbsp;

MiroFishThe team is recruiting full-time/internships long-term,If you are interested in multi-Agent applications,Welcome to submit your resume to:**mirofish@shanda.com**

## 📄 Acknowledgments

**MiroFish Received strategic support and incubation from Shanda Group!**

MiroFish The simulation engine consists of **[OASIS](https://github.com/camel-ai/oasis)** drive,We sincerely thank the CAMEL-AI team for their open source contributions!

## 📈 Project statistics

<a href="https://www.star-history.com/#666ghj/MiroFish&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&legend=top-left" />
 </picture>
</a>
