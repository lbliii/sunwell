// Test file for magnetic search experiment
/**
 * Service for managing user operations.
 * @class
 */
class UserService {
    /**
     * Create a UserService.
     * @param {Database} db - The database connection.
     */
    constructor(db) {
        this.db = db;
    }

    /**
     * Get a user by ID.
     * @param {string} id - The user ID.
     * @returns {Promise<User>} The user object.
     */
    async getUser(id) {
        return this.db.find(id);
    }

    /**
     * Create a new user.
     * @param {Object} data - The user data.
     * @returns {Promise<User>} The created user.
     */
    async createUser(data) {
        return this.db.insert(data);
    }

    /**
     * Delete a user.
     * @param {string} id - The user ID.
     */
    async deleteUser(id) {
        return this.db.delete(id);
    }
}

/**
 * Validate an email address.
 * @param {string} email - The email to validate.
 * @returns {boolean} True if valid.
 */
function validateEmail(email) {
    return email.includes('@') && email.includes('.');
}

/**
 * Format a user's display name.
 */
const formatDisplayName = (user) => {
    return `${user.firstName} ${user.lastName}`;
};

// Usage example
const service = new UserService(database);
const user = await service.getUser('123');
const isValid = validateEmail(user.email);
