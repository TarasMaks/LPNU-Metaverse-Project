// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title CanonicalIdentityNFT
/// @notice ERC-721-style non-fungible token representing a subject's
///         canonical identity.  Each token is linked to a PUF (Physically
///         Unclonable Function) commitment derived from biometric
///         authentication, creating an immutable binding between the
///         physical subject and their digital twin.
///
///         Follows the principles of ERC-721 and ERC-1155 for maximum
///         interoperability across metaverse platforms.
contract CanonicalIdentityNFT {
    struct IdentityToken {
        address owner;
        bytes32 pufCommitment;
        string metadataURI;
        bool active;
        uint256 mintedAt;
    }

    mapping(uint256 => IdentityToken) public tokens;
    mapping(address => uint256) public ownerToToken;
    mapping(bytes32 => bool) public commitmentUsed;

    uint256 public nextTokenId;
    address public admin;

    event IdentityMinted(
        uint256 indexed tokenId,
        address indexed owner,
        bytes32 indexed pufCommitment,
        string metadataURI,
        uint256 timestamp
    );

    event IdentityRevoked(uint256 indexed tokenId, uint256 timestamp);

    event MetadataUpdated(uint256 indexed tokenId, string newURI, uint256 timestamp);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Not authorised");
        _;
    }

    modifier onlyTokenOwner(uint256 tokenId) {
        require(tokens[tokenId].owner == msg.sender, "Not token owner");
        require(tokens[tokenId].active, "Token revoked");
        _;
    }

    constructor() {
        admin = msg.sender;
        nextTokenId = 1;
    }

    /// @notice Mint a new canonical identity NFT.
    /// @param to The wallet address to receive the token.
    /// @param pufCommitment The PUF commitment hash (biometric binding).
    /// @param metadataURI Off-chain metadata URI (e.g. IPFS CID).
    /// @return tokenId The ID of the newly minted token.
    function mintIdentity(
        address to,
        bytes32 pufCommitment,
        string calldata metadataURI
    ) external onlyAdmin returns (uint256 tokenId) {
        require(to != address(0), "Zero address");
        require(!commitmentUsed[pufCommitment], "PUF commitment already used");
        require(ownerToToken[to] == 0, "Address already has identity");

        tokenId = nextTokenId++;

        tokens[tokenId] = IdentityToken({
            owner: to,
            pufCommitment: pufCommitment,
            metadataURI: metadataURI,
            active: true,
            mintedAt: block.timestamp
        });

        ownerToToken[to] = tokenId;
        commitmentUsed[pufCommitment] = true;

        emit IdentityMinted(tokenId, to, pufCommitment, metadataURI, block.timestamp);
    }

    /// @notice Verify a canonical identity token.
    /// @param tokenId The token ID to verify.
    /// @return owner The token owner address.
    /// @return pufCommitment The PUF commitment hash.
    /// @return active Whether the token is active.
    function verifyIdentity(uint256 tokenId)
        external
        view
        returns (address owner, bytes32 pufCommitment, bool active)
    {
        IdentityToken storage t = tokens[tokenId];
        return (t.owner, t.pufCommitment, t.active);
    }

    /// @notice Revoke a canonical identity token.
    /// @param tokenId The token ID to revoke.
    function revokeIdentity(uint256 tokenId) external onlyAdmin {
        require(tokens[tokenId].active, "Token not active");
        tokens[tokenId].active = false;
        emit IdentityRevoked(tokenId, block.timestamp);
    }

    /// @notice Update the metadata URI of an identity token.
    /// @param tokenId The token ID to update.
    /// @param newURI The new metadata URI.
    function updateMetadata(uint256 tokenId, string calldata newURI)
        external
        onlyTokenOwner(tokenId)
    {
        tokens[tokenId].metadataURI = newURI;
        emit MetadataUpdated(tokenId, newURI, block.timestamp);
    }
}
