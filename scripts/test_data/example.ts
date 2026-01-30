// TypeScript test file for magnetic search
interface User {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
}

interface Database {
    find(id: string): Promise<User>;
    insert(data: Partial<User>): Promise<User>;
    delete(id: string): Promise<void>;
}

/**
 * Authentication service for handling user auth.
 */
class AuthService {
    private tokenStore: Map<string, string> = new Map();

    constructor(private userService: UserService) {}

    /**
     * Authenticate a user with credentials.
     */
    async login(email: string, password: string): Promise<string> {
        const user = await this.userService.findByEmail(email);
        if (!user) throw new Error('User not found');
        const token = this.generateToken(user);
        this.tokenStore.set(user.id, token);
        return token;
    }

    /**
     * Log out a user.
     */
    async logout(userId: string): Promise<void> {
        this.tokenStore.delete(userId);
    }

    private generateToken(user: User): string {
        return `token_${user.id}_${Date.now()}`;
    }
}

// Arrow function with types
const hashPassword = async (password: string): Promise<string> => {
    return `hashed_${password}`;
};
