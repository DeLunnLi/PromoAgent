import { summarize } from 'repo-pulse';

const result = await summarize('.');
console.log(result.tweetPack.singleTweet);
