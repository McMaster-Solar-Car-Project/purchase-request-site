/** @type {import('tailwindcss').Config} */
// needed for tailwind css to find the files to build + gives editor + autocomplete tips
module.exports = {
  content: [
    "./src/templates/**/*.html",
    "./src/static/js/**/*.js",
  ],
}
