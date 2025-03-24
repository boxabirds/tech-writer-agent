// Sample JavaScript file for testing

/**
 * A simple function that returns a greeting
 * @param {string} name - The name to greet
 * @returns {string} A greeting message
 */
function greet(name) {
  return `Hello, ${name}!`;
}

/**
 * A simple class for testing
 */
class Person {
  /**
   * Create a person
   * @param {string} name - The person's name
   * @param {number} age - The person's age
   */
  constructor(name, age) {
    this.name = name;
    this.age = age;
  }

  /**
   * Get a description of the person
   * @returns {string} Description
   */
  describe() {
    return `${this.name} is ${this.age} years old.`;
  }
}

// Example usage
const person = new Person("John", 30);
console.log(greet(person.name));
console.log(person.describe());
