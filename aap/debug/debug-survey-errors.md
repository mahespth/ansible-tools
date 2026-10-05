# Issues with 'error' appearing in the surveys

This code intercepts the survey data coming from the AWX backend API right inside your browser window. Before the React engine can step into it and blow up the screen, this script evaluates every object in the survey array and prints out a giant red error message telling you exactly which index name and variable has dropped the default key.


```javascript
(function() {
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    if (args[0] && args[0].includes('survey_spec')) {
      const clone = response.clone();
      try {
        const data = await clone.json();
        console.log("=== AWX SURVEY OBJECT ENGINE ===");
        data.spec.forEach((question, index) => {
          if (question.default === undefined) {
            console.error(`💥 CRASH TRIGGER FOUND at Index [${index}] (${question.question_name}): Object is completely missing the "default" property!`, question);
          } else {
            console.log(`✅ Valid Question [${index}] (${question.question_name}):`, question);
          }
        });
      } catch (e) {}
    }
    return response;
  };
```


})();

