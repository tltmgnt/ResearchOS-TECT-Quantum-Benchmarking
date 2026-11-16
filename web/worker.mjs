import{analyze}from'./model.mjs';
self.onmessage=event=>{try{self.postMessage({result:analyze(event.data)})}catch(error){self.postMessage({error:error.message})}};
